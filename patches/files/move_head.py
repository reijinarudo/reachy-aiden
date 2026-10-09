# Modified by Reginald Finley, Sr. (2026) for the reachy-aiden project.
# Original file: reachy_mini_conversation_app/tools/move_head.py, version 0.6.2,
# Copyright Pollen Robotics, licensed under the Apache License 2.0
# (see third_party/reachy_mini_conversation_app/LICENSE).
# Changes: returns the head to center before each new direction, gentler
# "down" angle, fixed move durations, and waits for the move to finish.
import asyncio
import logging
from typing import Any, Dict, Tuple, Literal

import numpy as np
from reachy_mini.utils import create_head_pose

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies
from reachy_mini_conversation_app.dance_emotion_moves import GotoQueueMove

logger = logging.getLogger(__name__)

Direction = Literal["left", "right", "up", "down", "front"]


class MoveHead(Tool):
    """Move head in a given direction. Pauses face tracking internally."""

    name = "move_head"
    description = "Move your head in a given direction: left, right, up, down or front."
    parameters_schema = {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["left", "right", "up", "down", "front"],
            },
        },
        "required": ["direction"],
    }

    DELTAS: Dict[str, Tuple[int, int, int, int, int, int]] = {
        "left": (0, 0, 0, 0, 0, 40),
        "right": (0, 0, 0, 0, 0, -40),
        "up": (0, 0, 0, 0, -30, 0),
        "down": (0, 0, 0, 0, 15, 0),
        "front": (0, 0, 0, 0, 0, 0),
    }

    HOME_DURATION = 1.5
    MOVE_DURATION = 2.0
    SETTLE_DELAY = 0.4

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        direction_raw = kwargs.get("direction")
        if not isinstance(direction_raw, str):
            return {"error": "direction must be a string"}
        direction: Direction = direction_raw  # type: ignore[assignment]
        logger.info("Tool call: move_head direction=%s", direction)

        deltas = self.DELTAS.get(direction, self.DELTAS["front"])
        target = create_head_pose(*deltas, degrees=True)
        home = create_head_pose(0, 0, 0, 0, 0, 0, degrees=True)

        camera_worker = deps.camera_worker
        was_tracking = False
        if camera_worker is not None:
            was_tracking = getattr(camera_worker, "head_tracking_enabled", False)
            if was_tracking:
                camera_worker.set_head_tracking_enabled(False)
                await asyncio.sleep(self.SETTLE_DELAY)

        try:
            movement_manager = deps.movement_manager
            current_head_pose = deps.reachy_mini.get_current_head_pose()
            _, current_antennas = deps.reachy_mini.get_current_joint_positions()
            near_home = np.allclose(current_head_pose, home, atol=0.1)

            total_duration = self.MOVE_DURATION
            if direction != "front" and not near_home:
                return_home = GotoQueueMove(
                    target_head_pose=home,
                    start_head_pose=current_head_pose,
                    target_antennas=(0, 0),
                    start_antennas=(current_antennas[0], current_antennas[1]),
                    target_body_yaw=0,
                    start_body_yaw=current_antennas[0],
                    duration=self.HOME_DURATION,
                )
                movement_manager.queue_move(return_home)

                goto_move = GotoQueueMove(
                    target_head_pose=target,
                    start_head_pose=home,
                    target_antennas=(0, 0),
                    start_antennas=(0, 0),
                    target_body_yaw=0,
                    start_body_yaw=0,
                    duration=self.MOVE_DURATION,
                )
                movement_manager.queue_move(goto_move)
                total_duration = self.HOME_DURATION + self.MOVE_DURATION
            else:
                goto_move = GotoQueueMove(
                    target_head_pose=target,
                    start_head_pose=current_head_pose,
                    target_antennas=(0, 0),
                    start_antennas=(current_antennas[0], current_antennas[1]),
                    target_body_yaw=0,
                    start_body_yaw=current_antennas[0],
                    duration=self.MOVE_DURATION,
                )
                movement_manager.queue_move(goto_move)

            movement_manager.set_moving_state(total_duration)
            await asyncio.sleep(total_duration)

            return {"status": f"looking {direction}"}
        except Exception as e:
            logger.error("move_head failed")
            return {"error": f"move_head failed: {type(e).__name__}: {e}"}
        finally:
            if was_tracking and camera_worker is not None:
                camera_worker.set_head_tracking_enabled(True)
