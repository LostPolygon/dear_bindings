import code_dom
import utils
import sys


# This modifier finds any overloaded functions with identical names and disambiguates them
def apply(dom_root, name_suffix_remaps):
    # Find all functions with name collisions

    functions_by_name = {}  # Contains lists of functions

    for function in dom_root.list_all_children_of_type(code_dom.DOMFunctionDeclaration):
        if function.name not in functions_by_name:
            # Create list
            functions_by_name[function.name] = [function]
        else:
            # Add to list
            functions_by_name[function.name].append(function)

    # Resolve collisions

    for functions in functions_by_name.values():
        if len(functions) < 2:
            continue  # No collision

        # Count the number of arguments that are identical across all overloads
        num_common_args = 0
        finished_common_arguments = False
        while num_common_args < len(functions[0].arguments):
            for function in functions:
                if num_common_args >= len(function.arguments):
                    finished_common_arguments = True
                    break  # Ran out of arguments
                if function.arguments[num_common_args].arg_type.to_c_string() != \
                        functions[0].arguments[num_common_args].arg_type.to_c_string():
                    finished_common_arguments = True
                    break  # Arguments don't match
            if finished_common_arguments:
                break
            num_common_args += 1

        # Find the function in the set with the smallest argument count
        lowest_arg_count = sys.maxsize
        lowest_arg_function = None
        for function in functions:
            if len(function.arguments) < lowest_arg_count:
                lowest_arg_count = len(function.arguments)
                lowest_arg_function = function

        # Add suffixes based on non-common arguments

        for function in functions:

            # Do not alter the name of the function with the fewest arguments
            if function == lowest_arg_function:
                continue

            suffix = ""
            for i in range(num_common_args, len(function.arguments)):
                if not function.arguments[i].is_varargs:  # Don't try and append a suffix for ... arguments
                    # Check to see if the full type name is in the remap list, and if so remap it
                    full_name = function.arguments[i].arg_type.to_c_string()
                    if full_name in name_suffix_remaps:
                        suffix_name = name_suffix_remaps[full_name]
                    else:
                        # Otherwise make a best guess
                        suffix_name = function.arguments[i].arg_type.get_primary_type_name()
                        # Capitalise the first letter of the name
                        suffix_name = suffix_name[0].upper() + suffix_name[1:]
                        # Slight bodge to differentiate pointers
                        if function.arguments[i].arg_type.to_c_string().endswith('*'):
                            suffix_name += "Ptr"
                    suffix += utils.sanitise_name_for_identifier(suffix_name)
            function.name += suffix

        # Semi-special case - if we have exactly two functions that still clash at this point, and they differ in
        # the const-ness of their return type, then add _Const to one

        if (len(functions) == 2) and (functions[0].name == functions[1].name):
            if functions[0].return_type.is_const() != functions[1].return_type.is_const():
                if functions[0].return_type.is_const():
                    functions[0].name += "_Const"
                else:
                    functions[1].name += "_Const"

        # Verify we now have no name clashes
        # (note that this only checks that we resolved the collisions between the functions that were initially
        # overloaded, and doesn't check for the possibility that a previously non-colliding function now collides)

        new_names = {}

        for function in functions:
            if function.name in new_names:
                print("Unresolved collision between these functions:")
                for print_function in functions:
                    print(print_function.name + " : " + str(print_function))
                raise Exception("Unresolved function name collision")

            new_names[function.name] = function
