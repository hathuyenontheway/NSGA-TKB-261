""" 
This test just checks the assign_students_fast(), it does not test the assign_students_exact().
I will add more tests for assign_students_exact() later.
"""
import pytest
from unittest.mock import patch, MagicMock
from core.models import StudentAssignment
from core.assignment import (
    assign_students_fast, 
    AssignmentResult, 
    Occurrence, 
    _ClassGroup
)

@pytest.fixture
def mock_environment():
    """
    Fixture creates a controlled testing environment.
    Scenario:
    - CS101: Capacity = 2 (Will test Capacity Overflow).
    - CS102: Day 2, Slots 1-3, Campus 1.
    - CS103: Day 2, Slots 2-4, Campus 1 (Time Conflict with CS102).
    - CS104: Day 2, Slots 6-8, Campus 2 (Campus Conflict with CS102: Gap is only 2 slots).
    """
    # 1. Create realistic Occurrence objects
    occ_cs101 = Occurrence(session_id=1, section_id="CS101-01", course_id="CS101", teacher_id="T1", room_id="R1", campus=1, day=3, start_slot=1, end_slot=3, week=1)
    occ_cs102 = Occurrence(session_id=2, section_id="CS102-01", course_id="CS102", teacher_id="T1", room_id="R2", campus=1, day=2, start_slot=1, end_slot=3, week=1)
    occ_cs103 = Occurrence(session_id=3, section_id="CS103-01", course_id="CS103", teacher_id="T2", room_id="R3", campus=1, day=2, start_slot=2, end_slot=4, week=1)
    occ_cs104 = Occurrence(session_id=4, section_id="CS104-01", course_id="CS104", teacher_id="T3", room_id="R4", campus=2, day=2, start_slot=6, end_slot=8, week=1)

    # 2. Mock the grouped classes output from _build_class_groups
    groups_by_course = {
        "CS101": [_ClassGroup(course_id="CS101", section_id="CS101-01", lab_section_id=None, capacity=2, occurrences=[occ_cs101])],
        "CS102": [_ClassGroup(course_id="CS102", section_id="CS102-01", lab_section_id=None, capacity=10, occurrences=[occ_cs102])],
        "CS103": [_ClassGroup(course_id="CS103", section_id="CS103-01", lab_section_id=None, capacity=10, occurrences=[occ_cs103])],
        "CS104": [_ClassGroup(course_id="CS104", section_id="CS104-01", lab_section_id=None, capacity=10, occurrences=[occ_cs104])],
    }

    # 3. Create a Mock ProblemInstance
    problem = MagicMock()
    problem.minimum_empty_slots = 3  # Requires at least 3 free slots to travel between campuses
    
    # Priority setup: 
    # SV_VIP (3 courses) > SV_MID (2 courses) > SV_LOW (1 course)
    problem.student_to_courses = {
        "SV_VIP": ["CS101", "CS102", "CS104"], # High priority
        "SV_MID": ["CS101", "CS102", "CS103"], # Medium priority
        "SV_LOW": ["CS101"]                    # Low priority
    }
    
    # Dummy chromosome
    chromosome = MagicMock()
    
    return problem, chromosome, groups_by_course


# Patching internal functions to use our mocked environment instead of complex real data
@patch("core.assignment._build_class_groups")
@patch("core.assignment.group_by_key")
@patch("core.assignment.expand_occurrences")
def test_student_priority_and_capacity_overflow(mock_expand, mock_group, mock_build, mock_environment):
    """
    Test that students with more requested courses get priority when classes are full.
    """
    problem, chromosome, groups_by_course = mock_environment
    mock_build.return_value = groups_by_course
    
    result = assign_students_fast(problem, chromosome)
    
    # Expected: CS101 capacity is 2. Requested by VIP, MID, LOW.
    # VIP and MID should get it. LOW should fail.
    cs101_assigned = [a.student_id for a in result.assignments if a.course_id == "CS101"]
    cs101_unfulfilled = [a.student_id for a in result.unfulfilled if a.course_id == "CS101"]
    
    assert len(cs101_assigned) == 2, "CS101 should not exceed capacity of 2"
    assert "SV_VIP" in cs101_assigned, "SV_VIP has highest priority"
    assert "SV_MID" in cs101_assigned, "SV_MID has medium priority"
    
    assert len(cs101_unfulfilled) == 1
    assert "SV_LOW" in cs101_unfulfilled, "SV_LOW has lowest priority and should be dropped"


@patch("core.assignment._build_class_groups")
@patch("core.assignment.group_by_key")
@patch("core.assignment.expand_occurrences")
def test_time_conflict_rejection(mock_expand, mock_group, mock_build, mock_environment):
    """
    Test that a student is not assigned to two courses with overlapping time slots.
    """
    problem, chromosome, groups_by_course = mock_environment
    mock_build.return_value = groups_by_course
    
    result = assign_students_fast(problem, chromosome)
    
    # Expected: SV_MID requests CS102 (slots 1-3) and CS103 (slots 2-4).
    # Since CS102 is processed first (dict order/sorting), CS103 should trigger a conflict.
    mid_assigned = [a.course_id for a in result.assignments if a.student_id == "SV_MID"]
    mid_unfulfilled = [a.course_id for a in result.unfulfilled if a.student_id == "SV_MID"]
    
    assert "CS102" in mid_assigned, "CS102 should be assigned successfully"
    assert "CS103" in mid_unfulfilled, "CS103 must be rejected due to time conflict"
    assert "CS103" not in mid_assigned, "Student cannot have conflicting schedules"


@patch("core.assignment._build_class_groups")
@patch("core.assignment.group_by_key")
@patch("core.assignment.expand_occurrences")
def test_campus_travel_gap_rejection(mock_expand, mock_group, mock_build, mock_environment):
    """
    Test that a student is not assigned consecutive classes at different campuses 
    without enough travel time.
    """
    problem, chromosome, groups_by_course = mock_environment
    mock_build.return_value = groups_by_course
    
    result = assign_students_fast(problem, chromosome)
    
    # Expected: SV_VIP requests CS102 (Campus 1, Ends slot 3) & CS104 (Campus 2, Starts slot 6).
    # Gap = 6 - 3 - 1 = 2 slots. The system requires minimum_empty_slots = 3.
    # CS104 must be rejected.
    vip_assigned = [a.course_id for a in result.assignments if a.student_id == "SV_VIP"]
    vip_unfulfilled = [a.course_id for a in result.unfulfilled if a.student_id == "SV_VIP"]
    
    assert "CS102" in vip_assigned, "CS102 should be assigned successfully"
    assert "CS104" in vip_unfulfilled, "CS104 must be rejected due to campus travel conflict"
    assert "CS104" not in vip_assigned, "Student cannot teleport between campuses"