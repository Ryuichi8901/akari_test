#!/usr/bin/env python3

import grpc
import json
import threading
import sys
import os
import time
from typing import Any
from akari_client import AkariClient
from akari_client.color import Colors
from akari_client.position import Positions

from depthai_handface.HandFaceTracker import HandFaceTracker
from depthai_handface.HandFaceRenderer import HandFaceRenderer

sys.path.append(os.path.join(os.path.dirname(__file__), "akari_motion_server/lib/grpc"))
import motion_server_pb2
import motion_server_pb2_grpc

json_path = "log/log.json"

motion_server_port = "localhost:50055"
channel = grpc.insecure_channel(motion_server_port)
stub = motion_server_pb2_grpc.MotionServerServiceStub(channel)
akari = AkariClient()
m5 = akari.m5stack


def display_good_count(num) -> None:
    """
    いいねの数を表示する

    Args:
        num: int 表示するいいねの数

    """
    m5.set_display_text(
        text=str(num),
        pos_x=Positions.CENTER,
        pos_y=Positions.CENTER,
        size=12,
        text_color=Colors.RED,
        back_color=Colors.WHITE,
        refresh=True,
    )
    m5.set_display_text(
        text="いいね!",
        pos_x=Positions.BOTTOM,
        pos_y=Positions.RIGHT,
        size=5,
        text_color=Colors.BLACK,
        back_color=Colors.WHITE,
        refresh=False,
    )


def good_update(num: int) -> None:
    """
    いいねの数を更新する

    Args:
        num: int いいねの数
    """
    motion = "nod"
    print("Send motion " + str(motion))
    try:
        reply = stub.SetMotion(
            motion_server_pb2.SetMotionRequest(
                name=motion, priority=3, repeat=False, clear=True
            )
        )
    except Exception as e:
        print("akari motion server set motion error")
    m5.set_display_text(
        text="Thank you!",
        pos_x=Positions.CENTER,
        pos_y=Positions.CENTER,
        size=5,
        text_color=Colors.RED,
        back_color=Colors.WHITE,
        refresh=True,
        sync=True,
    )
    time.sleep(1)
    display_good_count(num)
    result = {"good_count": num}
    with open(json_path, mode="wt", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def main() -> None:
    """
    メイン関数
    """

    tracker = HandFaceTracker(
        input_src=None,
        double_face=False,
        use_face_pose=False,
        use_gesture=True,
        xyz=True,
        with_attention=False,
        nb_hands=2,
        trace=0,
    )
    json_open = open(json_path, "r")
    try:
        log = json.load(json_open)
    except json.JSONDecodeError:
        log = {"good_count": 0}
    total_good_count = 0
    if log["good_count"] is not None:
        total_good_count = log["good_count"]

    renderer = HandFaceRenderer(tracker=tracker, output=None)
    HAND_GOOD_THRESHOLD = 5  # この回数以上OKが検出されたら1いいねとカウント
    HAND_ERROR_THRESHOLD = (
        3  # HAND_GOOD_THRESHOLDこの回数以上OK以外が検出されたらリセット
    )
    GOOD_LOCK_TIME = 2  # いいね後のロック時間
    last_count_time = time.time()
    hand_good_count = [0, 0]  # OKのカウント回数[左手、右手]
    hand_good_error_count = [0, 0]  # OKが抜けた回数[左手、右手]
    display_good_count(total_good_count)
    while True:
        frame, faces, hands = tracker.next_frame()
        if frame is None:
            break
        # Draw face and hands
        frame = renderer.draw(frame, faces, hands)
        for hand in hands:
            hand_num = 0
            if hand.label == "left":
                hand_num = 0
            elif hand.label == "right":
                hand_num = 1
            else:
                continue
            gesture_result = hand.gesture
            if (
                gesture_result == "OK"
                and time.time() - last_count_time > GOOD_LOCK_TIME
            ):
                hand_good_count[hand_num] += 1
            else:
                hand_good_error_count[hand_num] += 1
            # OKの検出回数が一定回数になったらいいねを加算
            if hand_good_count[hand_num] > HAND_GOOD_THRESHOLD:
                last_count_time = time.time()
                total_good_count += 1
                hand_good_count[hand_num] = 0
                hand_good_error_count[hand_num] = 0
                good_thread = threading.Thread(
                    target=good_update, args=(total_good_count,)
                )
                good_thread.start()
            elif hand_good_error_count[hand_num] > HAND_ERROR_THRESHOLD:
                hand_good_count[hand_num] = 0
                hand_good_error_count[hand_num] = 0

        key = renderer.waitKey(delay=1)
        if key == 27 or key == ord("q"):
            good_thread.join()
            time.sleep(1)
            m5.set_display_image("/jpg/logo320.jpg")
            break

    renderer.exit()
    tracker.exit()


if __name__ == "__main__":
    main()
