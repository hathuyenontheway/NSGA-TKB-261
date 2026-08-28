from pathlib import Path
from data.prepare_data import prepare_data

DATA = Path(__file__).parents[1] / "data"


def test_prepare_current_snapshot():
    prepared = prepare_data(DATA, track="HK_CHINH", semester_id="HK1")
    assert len(prepared.courses) == 696
    assert len(prepared.rooms) == 496
    assert prepared.calendar
    assert all(rid in prepared.rooms for rooms in prepared.course_to_rooms.values() for rid in rooms)


def test_mapping_is_bidirectional():
    prepared = prepare_data(DATA, track="HK_CHINH", semester_id="HK1")
    for cid, rooms in prepared.course_to_rooms.items():
        for rid in rooms: assert cid in prepared.room_to_courses[rid]
