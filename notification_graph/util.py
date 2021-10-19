def make_parameter_type_error(parameter, parameter_name, parameter_type):
    return TypeError(
        f'parameter \'{parameter_name}\' should be instance of {parameter_type.__name__}, '
        f'get {parameter.__class__.__name__ if parameter is not None else "None"}')
