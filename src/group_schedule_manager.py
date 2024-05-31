from typing import List, Tuple, NewType


Start = NewType("Start", int)
Length = NewType("Length", int)
Slot = Tuple[Start, Length]
Schedule = List[Slot]


class GroupsScheduleManager:
    def __init__(
        self,
        user_schedules: List[Schedule] = [],
        group_schedule: Schedule = [],
    ) -> None:
        self.user_schedules = user_schedules
        self.group_schedule = group_schedule

    def compute_group_schedule(self) -> Schedule:
        # Transfer intervals from (start, length) to (start, end) representation
        all_slots = sorted([(s, s + l) for s, l in sum(self.user_schedules, [])])
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

        group_schedule = [(s, e - s) for s, e in group_schedule]
        self.group_schedule = group_schedule
        return group_schedule

    def add_user(self, user_schedule: Schedule) -> Schedule:
        if self.group_schedule is None:
            self.compute_group_schedule()
        self.user_schedules.append(user_schedule)
        user_schedules = self.user_schedules

        self.user_schedules = [self.group_schedule, user_schedule]
        self.compute_group_schedule()
        self.user_schedules = user_schedules

        return self.group_schedule
