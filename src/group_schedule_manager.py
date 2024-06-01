from typing import List, Tuple, NewType


Day = NewType("Day", int)
Start = NewType("Start", int)
Length = NewType("Length", int)
Slot = Tuple[Day, Start, Length]
Schedule = List[Slot]


class GroupsScheduleManager:
    def __init__(
        self,
        user_schedules: list[list[dict]] = [],
        group_schedule: list[dict] = [],
    ) -> None:
        self.user_schedules: List[Schedule] = [
            self.to_internal_representation(us) for us in user_schedules
        ]
        self.group_schedule = self.to_internal_representation(group_schedule)

    @staticmethod
    def to_internal_representation(time_slots: list[dict]) -> Schedule:
        return [(ts["day"], ts["start"], ts["length"]) for ts in time_slots]

    @staticmethod
    def from_internal_representation(time_slots: Schedule) -> list[dict]:
        return [
            {"_id": i, "day": d, "start": s, "length": l}
            for (i, (d, s, l)) in enumerate(time_slots)
        ]

    def compute_group_schedule(self) -> list[dict]:
        # Transfer intervals from (day, start, length) to (start, end) representation
        all_slots = sorted(
            [(d * 24 + s, d * 24 + s + l) for (d, s, l) in sum(self.user_schedules, [])]
        )
        if len(all_slots) == 0:
            return []
        group_schedule = []

        cur_start, cur_end = all_slots[0]
        for start, end in all_slots[1:]:
            if start <= cur_end:
                cur_end = max(cur_end, end)
            else:
                group_schedule.append((cur_start, cur_end))
                cur_start, cur_end = start, end
        group_schedule.append((cur_start, cur_end))

        # Transfer intervals back to (day, start, length) form
        dsl_group_schedule = []
        for s, e in group_schedule:
            day_start = s // 24
            hour_start = s % 24
            day_end = e // 24
            hour_end = e % 24

            if day_end > day_start:
                dsl_group_schedule.append((day_start, hour_start, 24 - hour_start))
                dsl_group_schedule.append((day_end, 0, hour_end))
            else:
                dsl_group_schedule.append(
                    (day_start, hour_start, hour_end - hour_start)
                )
        self.group_schedule = dsl_group_schedule
        return self.from_internal_representation(dsl_group_schedule)

    def add_user(self, user_schedule: list[dict]) -> list[dict]:
        _user_schedule = self.to_internal_representation(user_schedule)
        if self.group_schedule is None:
            self.compute_group_schedule()
        self.user_schedules.append(_user_schedule)
        user_schedules = self.user_schedules

        self.user_schedules = [self.group_schedule, _user_schedule]
        self.compute_group_schedule()
        self.user_schedules = user_schedules

        return self.from_internal_representation(self.group_schedule)
