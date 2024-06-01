import pytest

from src.group_schedule_manager import GroupsScheduleManager


@pytest.mark.parametrize(
    "u1,u2,u3,group",
    [
        ([], [], [], []),
        (
            [{"day": 1, "start": 1, "length": 2}],
            [{"day": 1, "start": 2, "length": 3}],
            [{"day": 1, "start": 0, "length": 1}],
            [{"day": 1, "start": 0, "length": 5}],
        ),
        (
            [{"day": 1, "start": 0, "length": 3}, {"day": 1, "start": 6, "length": 6}],
            [
                {"day": 1, "start": 1, "length": 3},
                {"day": 1, "start": 5, "length": 0.5},
            ],
            [{"day": 1, "start": 3, "length": 2.8}],
            [
                {"day": 1, "start": 0, "length": 5.8},
                {"day": 1, "start": 6, "length": 6},
            ],
        ),
    ],
)
def test_compute_group_schedule(u1, u2, u3, group):
    gsm = GroupsScheduleManager([u1, u2, u3])
    sched = gsm.compute_group_schedule()
    for i in range(len(group)):
        dg, sg, lg = tuple(group[i].values())
        print(tuple(sched[i].values()))
        sched[i].pop("_id")
        ds, ss, ls = tuple(sched[i].values())
        assert abs(dg - ds) <= 0.0001
        assert abs(sg - ss) <= 0.0001
        assert abs(lg - ls) <= 0.0001


@pytest.mark.parametrize(
    "u1,u2,u3,group,new_group",
    [
        ([], [], [], [], []),
        (
            [{"day": 1, "start": 1, "length": 2}],
            [{"day": 1, "start": 2, "length": 3}],
            [{"day": 1, "start": 0, "length": 1}],
            [{"day": 1, "start": 1, "length": 4}],
            [{"day": 1, "start": 0, "length": 5}],
        ),
        (
            [{"day": 1, "start": 0, "length": 3}, {"day": 1, "start": 6, "length": 6}],
            [
                {"day": 1, "start": 1, "length": 3},
                {"day": 1, "start": 5, "length": 0.5},
            ],
            [{"day": 1, "start": 3, "length": 2.8}],
            [
                {"day": 1, "start": 0, "length": 4},
                {"day": 1, "start": 5, "length": 0.5},
                {"day": 1, "start": 6, "length": 6},
            ],
            [
                {"day": 1, "start": 0, "length": 5.8},
                {"day": 1, "start": 6, "length": 6},
            ],
        ),
    ],
)
def test_add_user_to_group_schedule(u1, u2, u3, group, new_group):
    gsm = GroupsScheduleManager([u1, u2])
    sched = gsm.compute_group_schedule()
    for i in range(len(group)):
        dg, sg, lg = tuple(group[i].values())
        sched[i].pop("_id")
        ds, ss, ls = tuple(sched[i].values())
        assert abs(dg - ds) <= 0.0001
        assert abs(sg - ss) <= 0.0001
        assert abs(lg - ls) <= 0.0001
    new_sched = gsm.add_user(u3)
    for i in range(len(new_group)):
        dg, sg, lg = tuple(new_group[i].values())
        new_sched[i].pop("_id")
        ds, ss, ls = tuple(new_sched[i].values())
        assert abs(dg - ds) <= 0.0001
        assert abs(sg - ss) <= 0.0001
        assert abs(lg - ls) <= 0.0001
