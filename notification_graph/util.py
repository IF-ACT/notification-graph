from typing import Dict, Any


def check_type(arg, arg_type):
    if not isinstance(arg, arg_type):
        raise TypeError(f'expected {arg_type.__name__}, get {repr(arg)}')


def merge_dict_set_values(main: Dict[Any, set], branch: Dict[Any, set]):
    """Merge dict 'branch' into dict 'main'"""
    for k, v in branch.items():
        mv = main.get(k, None)
        if mv is None:
            main[k] = v
        else:
            mv |= v
