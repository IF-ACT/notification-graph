def check_type(arg, arg_type):
    if not isinstance(arg, arg_type):
        raise TypeError(f'expected {arg_type.__name__}, get {repr(arg)}')
