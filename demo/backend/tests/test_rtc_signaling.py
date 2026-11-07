from conftest import join, receive_type, send

OFFER = {"type": "offer", "sdp": "v=0"}


def joined_for(ws, participant_id):
    for _ in range(30):
        event = receive_type(ws, "participant.joined")
        if event["payload"]["id"] == participant_id:
            return event["payload"]
    raise AssertionError("participant.joined not received")


def test_reconnect_changes_connection_id_and_drops_stale_signals(client):
    client.cookies.clear()
    a = join(client)
    a_cookies = dict(client.cookies)
    client.cookies.clear()
    b = join(client)
    b_cookies = dict(client.cookies)

    client.cookies.clear()
    client.cookies.update(a_cookies)
    with client.websocket_connect("/ws/rooms/demo-room") as wa:
        first_a = joined_for(wa, a["participant_id"])
        client.cookies.clear()
        client.cookies.update(b_cookies)
        with client.websocket_connect("/ws/rooms/demo-room"):
            first_b = joined_for(wa, b["participant_id"])
            assert first_b["connection_id"] and first_b["connection_id"] != first_a["connection_id"]
            # B reconnects before the server notices the old socket is gone.
            with client.websocket_connect("/ws/rooms/demo-room") as wb:
                second_b = joined_for(wa, b["participant_id"])
                assert second_b["connection_state"] == "connected"
                assert second_b["connection_id"] != first_b["connection_id"]

                stale = {
                    "target_id": b["participant_id"],
                    "target_connection_id": first_b["connection_id"],
                    "description": OFFER,
                }
                send(wa, "rtc.offer", stale, "stale")
                assert receive_type(wa, "ack")["payload"] == {"delivered": False}

                fresh = {**stale, "target_connection_id": second_b["connection_id"]}
                send(wa, "rtc.offer", fresh, "fresh")
                assert receive_type(wa, "ack")["payload"] == {"delivered": True}
                offer = receive_type(wb, "rtc.offer")["payload"]
                assert offer["from_id"] == a["participant_id"]
                assert offer["from_connection_id"] == first_a["connection_id"]
                assert offer["description"] == OFFER


def test_signal_without_target_connection_is_still_delivered(client):
    client.cookies.clear()
    a = join(client)
    a_cookies = dict(client.cookies)
    client.cookies.clear()
    b = join(client)
    with client.websocket_connect("/ws/rooms/demo-room") as wb:
        receive_type(wb, "participant.joined")
        client.cookies.clear()
        client.cookies.update(a_cookies)
        with client.websocket_connect("/ws/rooms/demo-room") as wa:
            receive_type(wa, "participant.joined")
            send(wa, "rtc.ice", {"target_id": b["participant_id"], "candidate": {"candidate": ""}}, "ice")
            assert receive_type(wa, "ack")["payload"] == {"delivered": True}
            assert receive_type(wb, "rtc.ice")["payload"]["from_id"] == a["participant_id"]
