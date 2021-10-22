import unittest
from notification_graph.core import NotificationItem, NotificationGraph, NotificationType
from notification_graph.notification_behaviors import NotifyObservers


class BasicTests(unittest.TestCase):

    def test0_create_item(self):
        item = NotificationItem()
        self.assertIsNotNone(item)

    def test1_simple_red_point(self):
        attr_activate = 'activate'
        red_point = NotificationType('red_point', NotifyObservers(attr_activate))

        item0 = NotificationItem()
        item1 = NotificationItem()
        item2 = NotificationItem()

        mid_item0 = NotificationItem()
        mid_item1 = NotificationItem()
        mid_item2 = NotificationItem()

        item0.add_notification(red_point)
        item1.add_notification(red_point)
        item2.add_notification(red_point)

        item1.subscribe(mid_item0)
        item2.subscribe(mid_item2)
        mid_item2.subscribe(mid_item1)
        mid_item1.subscribe(item0)
        mid_item0.subscribe(item0)

        self.assertFalse(item1[red_point].get_attribute(attr_activate))
        item0[red_point].set_attribute(attr_activate, True)
        self.assertTrue(item1[red_point].get_attribute(attr_activate))
        self.assertTrue(item2[red_point].get_attribute(attr_activate))
        item0[red_point].set_attribute(attr_activate, False)
        self.assertFalse(item1[red_point].get_attribute(attr_activate))
        self.assertFalse(item2[red_point].get_attribute(attr_activate))
