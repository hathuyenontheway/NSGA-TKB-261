import pandas as pd

from classify_resources import classify_resources
from llm_client import GeminiClient
from parse_courses import parse_courses
from parse_rooms import parse_rooms


course_df = pd.read_csv(
    "../data/processed/mh.csv",
    dtype=str,
    encoding="utf-8-sig",
)

room_df = pd.read_csv(
    "../data/processed/room261.csv",
    dtype=str,
    encoding="utf-8-sig",
)

courses = parse_courses(course_df)
rooms = parse_rooms(room_df)

client = GeminiClient(
    model="gemini-2.5-flash",
    project='ga-hcmut',
    location='global'
)

course_mapping, room_mapping = classify_resources(
    courses=courses,
    rooms=rooms,
    client=client,
    course_batch_size=25,
    room_batch_size=25,
)

print(f"Course mappings: {len(course_mapping)}")
print(f"Room mappings: {len(room_mapping)}")