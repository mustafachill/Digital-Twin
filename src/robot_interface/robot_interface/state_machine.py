#!/usr/bin/env python3
"""
State Machine for Robot Interface

Implements the state machine for each robot in the assembly line.
States: IDLE -> PICKING -> HOLDING -> PLACING -> IDLE

Each robot operates independently and communicates with neighbors via pub/sub.
"""

from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import time


class RobotState(Enum):
    """Robot states for the assembly line"""
    IDLE = "IDLE"
    WAITING_FOR_OBJECT = "WAITING_FOR_OBJECT"
    PICKING = "PICKING"
    HOLDING = "HOLDING"
    WAITING_FOR_HANDOFF = "WAITING_FOR_HANDOFF"
    PLACING = "PLACING"
    ERROR = "ERROR"
    

class RobotSubState(Enum):
    """Sub-states for more detailed tracking"""
    NONE = "NONE"
    MOVING_TO_PICK = "MOVING_TO_PICK"
    CLOSING_GRIPPER = "CLOSING_GRIPPER"
    MOVING_TO_PLACE = "MOVING_TO_PLACE"
    OPENING_GRIPPER = "OPENING_GRIPPER"
    RETURNING_HOME = "RETURNING_HOME"


@dataclass
class StateTransition:
    """Represents a state transition"""
    from_state: RobotState
    to_state: RobotState
    trigger: str
    condition: Optional[Callable[[], bool]] = None
    action: Optional[Callable[[], None]] = None


class RobotStateMachine:
    """
    State machine for a single robot
    
    Handles state transitions and callbacks for the robot.
    """
    
    def __init__(self, robot_id: str, role: str = "transfer"):
        self.robot_id = robot_id
        self.role = role  # pick, transfer, place
        
        self._state = RobotState.IDLE
        self._sub_state = RobotSubState.NONE
        self._holding_object = False
        self._error_message = ""
        self._last_transition_time = time.time()
        
        # Callbacks
        self._on_state_change: Optional[Callable[[RobotState, RobotState], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Allowed transitions based on role
        self._setup_transitions()
    
    def _setup_transitions(self):
        """Setup allowed state transitions"""
        self.transitions: Dict[RobotState, Dict[str, RobotState]] = {
            RobotState.IDLE: {
                'object_detected': RobotState.WAITING_FOR_OBJECT,
                'start_pick': RobotState.PICKING,
                'handoff_request': RobotState.WAITING_FOR_OBJECT,
            },
            RobotState.WAITING_FOR_OBJECT: {
                'object_ready': RobotState.PICKING,
                'timeout': RobotState.IDLE,
                'error': RobotState.ERROR,
            },
            RobotState.PICKING: {
                'pick_complete': RobotState.HOLDING,
                'pick_failed': RobotState.IDLE,
                'error': RobotState.ERROR,
            },
            RobotState.HOLDING: {
                'downstream_ready': RobotState.WAITING_FOR_HANDOFF,
                'start_place': RobotState.PLACING,
                'error': RobotState.ERROR,
            },
            RobotState.WAITING_FOR_HANDOFF: {
                'handoff_accepted': RobotState.PLACING,
                'timeout': RobotState.HOLDING,
                'error': RobotState.ERROR,
            },
            RobotState.PLACING: {
                'place_complete': RobotState.IDLE,
                'place_failed': RobotState.HOLDING,
                'error': RobotState.ERROR,
            },
            RobotState.ERROR: {
                'reset': RobotState.IDLE,
                'recovered': RobotState.IDLE,
            },
        }
    
    @property
    def state(self) -> RobotState:
        return self._state
    
    @property
    def sub_state(self) -> RobotSubState:
        return self._sub_state
    
    @property
    def holding_object(self) -> bool:
        return self._holding_object
    
    @property
    def error_message(self) -> str:
        return self._error_message
    
    @property
    def is_ready_to_receive(self) -> bool:
        """Check if robot is ready to receive an object from upstream"""
        return self._state in [RobotState.IDLE, RobotState.WAITING_FOR_OBJECT]
    
    @property
    def is_ready_to_give(self) -> bool:
        """Check if robot is ready to give object to downstream"""
        return self._state == RobotState.HOLDING and self._holding_object
    
    def set_on_state_change(self, callback: Callable[[RobotState, RobotState], None]):
        """Set callback for state changes"""
        self._on_state_change = callback
    
    def set_on_error(self, callback: Callable[[str], None]):
        """Set callback for errors"""
        self._on_error = callback
    
    def trigger(self, event: str) -> bool:
        """
        Trigger a state transition
        
        Args:
            event: The event/trigger name
            
        Returns:
            True if transition was successful
        """
        if self._state not in self.transitions:
            return False
        
        allowed = self.transitions[self._state]
        if event not in allowed:
            return False
        
        old_state = self._state
        new_state = allowed[event]
        
        self._state = new_state
        self._last_transition_time = time.time()
        
        # Update holding_object based on state
        if new_state == RobotState.PICKING:
            pass  # Will be set on pick_complete
        elif event == 'pick_complete':
            self._holding_object = True
        elif event in ['place_complete', 'place_failed']:
            self._holding_object = False
        
        # Clear error on recovery
        if event in ['reset', 'recovered']:
            self._error_message = ""
        
        # Call callback
        if self._on_state_change:
            self._on_state_change(old_state, new_state)
        
        return True
    
    def set_error(self, message: str):
        """Set error state with message"""
        old_state = self._state
        self._state = RobotState.ERROR
        self._error_message = message
        self._last_transition_time = time.time()
        
        if self._on_error:
            self._on_error(message)
        
        if self._on_state_change:
            self._on_state_change(old_state, RobotState.ERROR)
    
    def set_sub_state(self, sub_state: RobotSubState):
        """Update sub-state for detailed tracking"""
        self._sub_state = sub_state
    
    def reset(self):
        """Reset state machine to IDLE"""
        old_state = self._state
        self._state = RobotState.IDLE
        self._sub_state = RobotSubState.NONE
        self._holding_object = False
        self._error_message = ""
        self._last_transition_time = time.time()
        
        if self._on_state_change:
            self._on_state_change(old_state, RobotState.IDLE)
    
    def get_status_dict(self) -> Dict[str, Any]:
        """Get current status as dictionary"""
        return {
            'robot_id': self.robot_id,
            'role': self.role,
            'state': self._state.value,
            'sub_state': self._sub_state.value,
            'holding_object': self._holding_object,
            'ready_to_receive': self.is_ready_to_receive,
            'ready_to_give': self.is_ready_to_give,
            'has_error': self._state == RobotState.ERROR,
            'error_message': self._error_message,
            'last_transition': self._last_transition_time,
        }


def main():
    """Test state machine"""
    sm = RobotStateMachine("test_robot", "transfer")
    
    def on_change(old, new):
        print(f"State: {old.value} -> {new.value}")
    
    sm.set_on_state_change(on_change)
    
    print("Testing state machine...")
    print(f"Initial: {sm.state.value}")
    
    sm.trigger('object_detected')
    sm.trigger('object_ready')
    sm.trigger('pick_complete')
    print(f"Holding: {sm.holding_object}")
    sm.trigger('downstream_ready')
    sm.trigger('handoff_accepted')
    sm.trigger('place_complete')
    print(f"Final: {sm.state.value}")
    

if __name__ == '__main__':
    main()







