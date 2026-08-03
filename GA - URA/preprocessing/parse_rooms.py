from __future__ import annotations

import pandas as pd

from models.room import Room


_REQUIRED_COLUMNS = {
    "Cơ sở",
    "Sức chứa",
    "Tính chất phòng",
    "Mã Phòng",
}

def _parse_room_type(room_name: str) -> str:
    name = room_name.upper()

    lab_keywords = (
        "PTN",
        "THỰC HÀNH",
        "THUC HANH",
        "PHÒNG MÁY",
        "PHONG MAY",
        "MÁY TÍNH",
        "MAY TINH",
        "TH ",
        "XƯỞNG",
        "XUONG",
        "LAB",
    )

    if any(keyword in name for keyword in lab_keywords):
        return "LAB"

    return "LECTURE"

def _normalize_text(value: object) -> str:
    """Chuẩn hóa dữ liệu dạng chuỗi."""
    if pd.isna(value):
        return ""

    return str(value).strip()


def _parse_capacity(value: object) -> int:
    """Chuyển sức chứa thành số nguyên dương."""
    try:
        capacity = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Không thể chuyển sức chứa {value!r} thành số nguyên."
        ) from exc

    if capacity <= 0:
        raise ValueError(
            f"Sức chứa phải lớn hơn 0, nhận được {capacity}."
        )

    return capacity


def _parse_campus(value: object) -> int:
    """
    Chuyển giá trị cột 'Cơ sở' thành campus.

    Hỗ trợ:
        1
        2
        CS1
        CS2
        Cơ sở 1
        Cơ sở 2
    """
    text = str(value).strip().upper()

    mapping = {
        "1": 1,
        "1.0": 1,
        "CS1": 1,
        "CS 1": 1,
        "CƠ SỞ 1": 1,
        "CO SO 1": 1,

        "2": 2,
        "2.0": 2,
        "CS2": 2,
        "CS 2": 2,
        "CƠ SỞ 2": 2,
        "CO SO 2": 2,
    }

    if text in mapping:
        return mapping[text]

    try:
        return int(float(text))
    except Exception as exc:
        raise ValueError(
            f"Không nhận diện được cơ sở: {value!r}"
        ) from exc


def parse_rooms(df: pd.DataFrame) -> dict[str, Room]:

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "parse_rooms() yêu cầu đầu vào là pandas.DataFrame."
        )

    cleaned = df.copy()

    cleaned.columns = cleaned.columns.str.strip()

    missing_columns = _REQUIRED_COLUMNS.difference(cleaned.columns)

    if missing_columns:
        raise ValueError(
            "room261.csv thiếu các cột: "
            + ", ".join(sorted(missing_columns))
        )

    # Chỉ giữ các dòng đủ thông tin để tạo Room
    cleaned["Sức chứa"] = pd.to_numeric(
    cleaned["Sức chứa"],
    errors="coerce",
    )
    cleaned = cleaned.dropna(
        subset=[
            "Mã Phòng",
            "Cơ sở",
            "Sức chứa",
        ]
    )
    cleaned = cleaned[cleaned['Sức chứa'] > 0]
    cleaned = cleaned[cleaned['Mã Phòng'] != '------']
    rooms: dict[str, Room] = {}

    for row_number, row in cleaned.iterrows():

        room_id = _normalize_text(row["Mã Phòng"])

        if room_id in rooms:
            existing_room = rooms[room_id]

            # print(
            #     f"[WARNING] Trùng mã phòng {room_id!r} "
            #     f"tại dòng {row_number + 2}. "
            #     f"Giữ bản ghi trước: "
            #     f"capacity={existing_room.capacity}, "
            #     f"type={existing_room.room_type}. "
            #     f"Bỏ qua bản ghi hiện tại: "
            #     f"capacity={row['Sức chứa']!r}, "
            #     f"type={row['Tính chất phòng']!r}."
            # )

            continue

        room_type = _normalize_text(
            row["Tính chất phòng"]
        ).upper()

        if not room_type:
            room_type = "LECTURE"

        rooms[room_id] = Room(
            room_id=room_id,
            campus=_parse_campus(row["Cơ sở"]),
            capacity=_parse_capacity(row["Sức chứa"]),
            room_type=room_type,
        )

    return rooms