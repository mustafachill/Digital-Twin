# legacy/docs/ — superseded documentation

These are the v1 planning documents. **They are historical record, not guidance,
and several of them are wrong.**

They are kept because they show how the project's thinking developed, and
because `WORK_LOG.md` in particular records real technical findings about xArm
integration and `ros2_control` that were expensive to learn.

## Do not follow these

- `GOALS.md`, `PROJECT_CONTEXT.md`, `SCALABLE_ARCHITECTURE.md` — superseded by
  `what-we-are-doing.md`. Where they disagree with it, they are wrong.
- `WORK_LOG.md` — describes messages, services, and packages that were never
  actually created, and marks capabilities complete that no test ever proved.
  Read it for the debugging findings, not for status.
- `HIZLITEST.md`, `QUICK_CONTROL_GUIDE.md` — commands for a Gazebo Classic
  system that no longer exists.
- `BLENDER_TO_GAZEBO_GUIDE.md` — targets Gazebo Classic. The asset pipeline is
  redefined in `assets/README.md`.

Current documentation lives in `docs/`. The charter is `what-we-are-doing.md`.
