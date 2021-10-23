import unittest

from notification_graph.core import NotificationType, NotificationItem
from notification_graph.notification_behaviors import NotifySubscribers


class TestNotifySubscribers(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestNotifySubscribers, self).__init__(*args, **kwargs)
        self.attr_activate = 'activate'
        self.red_point = NotificationType('red_point', NotifySubscribers(self.attr_activate))

    def test0_simple_red_point(self):
        items = self.create_items(3, True)
        mid_items = self.create_items(3)

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
        items = self.create_items(3, True)

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
        items = self.create_items(3, True)
        mid_items = self.create_items(2)

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
        item0, item1 = self.create_items(2, True)
        mid_item = self.create_items(1)[0]

        item0.subscribe(mid_item)
        self.setRedPoint(item1, True)
        mid_item.subscribe(item1)
        self.assertRedPoint(item0, True)

    def create_items(self, num: int, add_red_point=False):
        items = [NotificationItem() for _ in range(num)]
        if add_red_point:
            for item in items:
                item.add_notification(self.red_point)
        return items

    def assertRedPoint(self, item: NotificationItem, activate: bool):
        self.assertEqual(item[self.red_point].get_attribute(self.attr_activate), activate,
                         f'should be {"activate" if activate else "inactivate"}')

    def setRedPoint(self, item: NotificationItem, activate: bool):
        item[self.red_point].set_attribute(self.attr_activate, activate)
