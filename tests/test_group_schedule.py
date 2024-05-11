import pytest

from src.group_schedule_manager import GroupsScheduleManager


@pytest.mark.parametrize(
    "u1,u2,u3,group",
    [
        ([], [], [], []),
        ([(1, 2)], [(2, 3)], [(0, 1)], [(0, 5)]),
        ([(0, 3), (6, 6)], [(1, 3), (5, 0.5)], [(3, 2.8)], [(0, 5.8), (6, 6)]),
    ],
)
def test_compute_group_schedule(u1, u2, u3, group):
    gsm = GroupsScheduleManager([u1, u2, u3])
    sched = gsm.compute_group_schedule()
    assert sched == group


@pytest.mark.parametrize(
    "u1,u2,u3,group,new_group",
    [
        ([], [], [], [], []),
        ([(1, 2)], [(2, 3)], [(0, 1)], [(1, 4)], [(0, 5)]),
        (
            [(0, 3), (6, 6)],
            [(1, 3), (5, 0.5)],
            [(3, 2.8)],
            [(0, 4), (5, 0.5), (6, 6)],
            [(0, 5.8), (6, 6)],
        ),
    ],
)
def test_add_user_to_group_schedule(u1, u2, u3, group, new_group):
    gsm = GroupsScheduleManager([u1, u2])
    sched = gsm.compute_group_schedule()
    assert sched == group
    new_sched = gsm.add_user(u3)
    assert new_sched == new_group
