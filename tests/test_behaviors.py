import unittest

from notification_graph.core import NotificationType, NotificationItem
from notification_graph.notification_behaviors import NotifySubscribers, CountAttribute


def create_items(num: int, add_attribute: NotificationType = None):
    items = [NotificationItem() for _ in range(num)]
    if add_attribute is not None:
        for item in items:
            item.add_notification(add_attribute)
    return items


class TestNotifySubscribers(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestNotifySubscribers, self).__init__(*args, **kwargs)
        self.attr_activate = 'activate'
        self.red_point = NotificationType('red_point', NotifySubscribers(self.attr_activate))

    def test0_simple_red_point(self):
        items = create_items(3, self.red_point)
        mid_items = create_items(3)

        items[1].subscribe(mid_items[0])
        items[2].subscribe(mid_items[2])
        mid_items[2].subscribe(mid_items[1])
        mid_items[1].subscribe(items[0])
        mid_items[0].subscribe(items[0])

        self.assertRedPoint(items[1], False)
        self.setRedPoint(items[0], True)
        self.assertRedPoint(items[1], True)
        self.assertRedPoint(items[2], True)
        self.setRedPoint(items[0], False)
        self.assertRedPoint(items[1], False)
        self.assertRedPoint(items[2], False)

    def test1_subscribe_multi_directly(self):
        items = create_items(3, self.red_point)

        items[0].subscribe(items[1])
        items[0].subscribe(items[2])

        self.assertRedPoint(items[0], False)
        self.setRedPoint(items[1], True)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[2], True)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[1], False)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[2], False)
        self.assertRedPoint(items[0], False)

    def test2_subscribe_multi_indirectly(self):
        items = create_items(3, self.red_point)
        mid_items = create_items(2)

        items[0].subscribe(mid_items[0])
        items[0].subscribe(mid_items[1])
        mid_items[0].subscribe(items[1])
        mid_items[1].subscribe(items[2])

        self.assertRedPoint(items[0], False)
        self.setRedPoint(items[1], True)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[2], True)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[1], False)
        self.assertRedPoint(items[0], True)
        self.setRedPoint(items[2], False)
        self.assertRedPoint(items[0], False)

    def test3_add_subscription_dynamically(self):
        item0, item1 = create_items(2, self.red_point)
        mid_item = create_items(1)[0]

        item0.subscribe(mid_item)
        self.setRedPoint(item1, True)
        mid_item.subscribe(item1)
        self.assertRedPoint(item0, True)

    def assertRedPoint(self, item: NotificationItem, activate: bool):
        self.assertEqual(item[self.red_point].get_attribute(self.attr_activate), activate,
                         f'should be {"activate" if activate else "inactivate"}')

    def setRedPoint(self, item: NotificationItem, activate: bool):
        item[self.red_point].set_attribute(self.attr_activate, activate)


class TestCountAttribute(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestCountAttribute, self).__init__(*args, **kwargs)
        self.counted_attr = 'activate'
        self.num_attr = 'count_activate'
        self.red_point = NotificationType('red_point', NotifySubscribers(self.counted_attr))
        self.red_counter = NotificationType('red_point', CountAttribute(activate=self.num_attr))

    def test0_simple_count(self):
        red_items = create_items(2, self.red_point)
        red_counter = create_items(1, self.red_counter)[0]

        red_counter.subscribe(red_items[0])
        red_counter.subscribe(red_items[1])

        self.assertEqual(0, self.get_count(red_counter))
        self.set_red_point(red_items[0], True)
        self.assertEqual(1, self.get_count(red_counter))
        self.set_red_point(red_items[1], True)
        self.assertEqual(2, self.get_count(red_counter))
        self.set_red_point(red_items[0], False)
        self.assertEqual(1, self.get_count(red_counter))

    def get_count(self, counter: NotificationItem):
        return counter[self.red_counter].get_attribute(self.num_attr)

    def set_red_point(self, red_point: NotificationItem, activate: bool):
        red_point[self.red_point].set_attribute(self.counted_attr, activate)
