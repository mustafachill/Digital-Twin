#!/usr/bin/env python3
"""
Config Loader for Fleet Manager

Loads and validates fleet configuration from YAML files.
Provides typed dataclasses for easy access to configuration.
"""

import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path


@dataclass
class Position:
    """3D position with orientation"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class RobotConfig:
    """Configuration for a single robot"""
    id: str
    type: str
    enabled: bool = True
    position: Position = field(default_factory=Position)
    add_gripper: bool = True
    gripper_type: str = "xarm_gripper"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RobotConfig':
        pos_data = data.get('position', {})
        position = Position(
            x=pos_data.get('x', 0.0),
            y=pos_data.get('y', 0.0),
            z=pos_data.get('z', 0.0),
            roll=pos_data.get('roll', 0.0),
            pitch=pos_data.get('pitch', 0.0),
            yaw=pos_data.get('yaw', 0.0)
        )
        config = data.get('config', {})
        return cls(
            id=data['id'],
            type=data['type'],
            enabled=data.get('enabled', True),
            position=position,
            add_gripper=config.get('add_gripper', True),
            gripper_type=config.get('gripper_type', 'xarm_gripper')
        )


@dataclass
class StationConfig:
    """Configuration for a workstation in the topology"""
    id: str
    robot: str
    role: str  # pick, transfer, place
    upstream: str  # Previous robot/conveyor ID
    downstream: str  # Next robot/conveyor ID
    sensor: str = ""
    pick_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.15])
    place_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.15])
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StationConfig':
        return cls(
            id=data['id'],
            robot=data['robot'],
            role=data['role'],
            upstream=data['upstream'],
            downstream=data['downstream'],
            sensor=data.get('sensor', ''),
            pick_position=data.get('pick_position', [0.0, 0.0, 0.15]),
            place_position=data.get('place_position', [0.0, 0.0, 0.15])
        )


@dataclass
class TopologyConfig:
    """Topology configuration defining robot relationships"""
    type: str  # chain, star, mesh, custom
    stations: List[StationConfig] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopologyConfig':
        stations = [StationConfig.from_dict(s) for s in data.get('stations', [])]
        return cls(
            type=data.get('type', 'chain'),
            stations=stations
        )
    
    def get_station_for_robot(self, robot_id: str) -> Optional[StationConfig]:
        """Get station config for a specific robot"""
        for station in self.stations:
            if station.robot == robot_id:
                return station
        return None
    
    def get_neighbors(self, robot_id: str) -> Dict[str, str]:
        """Get upstream and downstream neighbors for a robot"""
        station = self.get_station_for_robot(robot_id)
        if station:
            return {
                'upstream': station.upstream,
                'downstream': station.downstream
            }
        return {}


@dataclass
class ConveyorConfig:
    """Conveyor belt configuration"""
    enabled: bool = True
    length: float = 4.0
    width: float = 0.45
    speed: float = 0.1
    entry_point: List[float] = field(default_factory=lambda: [0.0, -1.8, 0.8])
    exit_point: List[float] = field(default_factory=lambda: [0.0, 1.8, 0.8])
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConveyorConfig':
        return cls(
            enabled=data.get('enabled', True),
            length=data.get('length', 4.0),
            width=data.get('width', 0.45),
            speed=data.get('speed', 0.1),
            entry_point=data.get('entry_point', [0.0, -1.8, 0.8]),
            exit_point=data.get('exit_point', [0.0, 1.8, 0.8])
        )


@dataclass
class SensorConfig:
    """Sensor configuration"""
    id: str
    type: str  # break_beam, proximity, camera
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    topic: str = ""
    
    @classmethod
    def from_dict(cls, sensor_id: str, data: Dict[str, Any]) -> 'SensorConfig':
        return cls(
            id=sensor_id,
            type=data.get('type', 'break_beam'),
            position=data.get('position', [0.0, 0.0, 0.0]),
            topic=data.get('topic', f'/sensors/{sensor_id}')
        )


@dataclass
class FleetConfig:
    """Complete fleet configuration"""
    name: str = "default_fleet"
    version: str = "1.0"
    robots: List[RobotConfig] = field(default_factory=list)
    topology: TopologyConfig = field(default_factory=TopologyConfig)
    conveyor: ConveyorConfig = field(default_factory=ConveyorConfig)
    sensors: List[SensorConfig] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FleetConfig':
        fleet_data = data.get('fleet', {})
        
        robots = [RobotConfig.from_dict(r) for r in fleet_data.get('robots', [])]
        
        topology = TopologyConfig.from_dict(data.get('topology', {}))
        
        conveyor = ConveyorConfig.from_dict(data.get('conveyor', {}))
        
        sensors = []
        for sensor_id, sensor_data in data.get('sensors', {}).items():
            sensors.append(SensorConfig.from_dict(sensor_id, sensor_data))
        
        return cls(
            name=fleet_data.get('name', 'default_fleet'),
            version=fleet_data.get('version', '1.0'),
            robots=robots,
            topology=topology,
            conveyor=conveyor,
            sensors=sensors
        )
    
    def get_enabled_robots(self) -> List[RobotConfig]:
        """Get only enabled robots"""
        return [r for r in self.robots if r.enabled]
    
    def get_robot_by_id(self, robot_id: str) -> Optional[RobotConfig]:
        """Get robot config by ID"""
        for robot in self.robots:
            if robot.id == robot_id:
                return robot
        return None


class ConfigLoader:
    """Loads fleet configuration from YAML files"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._fleet_config: Optional[FleetConfig] = None
        self._robot_types: Dict[str, Any] = {}
    
    def load(self) -> FleetConfig:
        """Load and parse the fleet configuration file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        self._fleet_config = FleetConfig.from_dict(data)
        return self._fleet_config
    
    def load_robot_types(self, robot_types_path: str) -> Dict[str, Any]:
        """Load robot type definitions"""
        path = Path(robot_types_path)
        if not path.exists():
            raise FileNotFoundError(f"Robot types file not found: {path}")
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        self._robot_types = data.get('robot_types', {})
        return self._robot_types
    
    def get_robot_type_config(self, robot_type: str) -> Dict[str, Any]:
        """Get configuration for a specific robot type"""
        return self._robot_types.get(robot_type, {})
    
    @property
    def fleet_config(self) -> Optional[FleetConfig]:
        return self._fleet_config
    
    @property
    def robot_types(self) -> Dict[str, Any]:
        return self._robot_types


def main():
    """Test config loading"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: config_loader.py <config_path>")
        return
    
    loader = ConfigLoader(sys.argv[1])
    config = loader.load()
    
    print(f"Fleet: {config.name} v{config.version}")
    print(f"Robots: {len(config.robots)}")
    for robot in config.robots:
        print(f"  - {robot.id}: {robot.type} at ({robot.position.x}, {robot.position.y}, {robot.position.z})")
    
    print(f"Topology: {config.topology.type}")
    for station in config.topology.stations:
        print(f"  - {station.id}: {station.robot} [{station.upstream}] -> [{station.downstream}]")


if __name__ == '__main__':
    main()







