from .common import *
from src import code_dom


# A function declaration
class DOMFunctionDeclaration(code_dom.element.DOMElement):
    def __init__(self):
        super().__init__()
        self.name = None
        self.return_type = None
        self.arguments = []
        self.initialiser_list_tokens = None  # List of tokens making up the initialiser list if one exists
        self.body = None
        self.is_const = False
        self.is_constexpr = False
        self.is_static = False
        self.is_inline = False
        self.is_operator = False
        self.is_constructor = False
        self.is_by_value_constructor = False  # Is this a by-value type constructor? (set during flattening)
        self.is_destructor = False
        self.is_imgui_api = False
        self.im_fmtargs = None
        self.im_fmtlist = None
        self.accessibility = None  # The function accessibility (if part of a class)
        self.original_class = None  # The class this function belonged to pre-flattening
        #                             (set when functions are flattened)
        self.is_default_argument_helper = False  # Set if this is an autogenerated function with arguments defaulted
        #                                         (see mod_generate_default_argument_functions)
        self.is_manual_helper = False  # Set if this is a manually-added helper function
        #                                (see mod_add_helper_functions for more details)
        self.has_imstr_helper = False  # Set if this is the ImStr variant of a function that has had a char* helper
        #                                generated (see mod_generate_imstr_helpers for more details)
        self.is_imstr_helper = False  # Set if this is a helper function that converts char* into ImStr
        #                                (see mod_generate_imstr_helpers for more details)

        self.function_name_alignment = 0  # Column to align the function name to (see mod_align_function_names)
        self.is_unformatted_helper = False # Set if this is a variant of a function accepting a format string with
        #                                  format string forced to '%s' and a single string argument

    # Parse tokens from the token stream given
    @staticmethod
    def parse(context, stream):
        checkpoint = stream.get_checkpoint()
        dom_element = DOMFunctionDeclaration()

        # Parse prefixes
        while True:
            prefix_token = stream.peek_token_of_type(["THING", "CONSTEXPR"])
            if prefix_token is None:
                break

            if prefix_token.value == 'IMGUI_API':
                stream.get_token()  # Eat token
                dom_element.is_imgui_api = True
            elif prefix_token.value == 'inline':
                stream.get_token()  # Eat token
                dom_element.is_inline = True
            elif prefix_token.value == 'static':
                stream.get_token()  # Eat token
                dom_element.is_static = True
            elif prefix_token.value == 'constexpr':
                stream.get_token()  # Eat token
                dom_element.is_constexpr = True
            elif prefix_token.value == 'operator':
                # Copy constructors can look like this "operator ImVec4() const;" and thus have "operator" as a prefix
                stream.get_token()  # Eat token
                dom_element.is_operator = True
            else:
                break

        # Check for a leading ~ as used on destructors
        name_prefix = ""
        leading_tilde = stream.get_token_of_type(["~"])
        if leading_tilde is not None:
            dom_element.tokens.append(leading_tilde)
            name_prefix = leading_tilde.value
            dom_element.is_destructor = True

        # Because constructors/destructors have no return type declaration, we need to peek ahead to see if the first
        # token is a type or the function name

        has_no_return_type = False
        name_token = stream.get_token_of_type(["THING"])
        if name_token is not None:
            if stream.peek_token_of_type(["LPAREN"]) is not None:
                # If we see a name-like-thing followed by a bracket, we assume this is a return-type-less function
                has_no_return_type = True
            stream.rewind_one_token()

        # If it has no return type and hasn't already been identified as a destructor, it must be a constructor
        if has_no_return_type and not dom_element.is_destructor:
            dom_element.is_constructor = True

        # Return type

        if not has_no_return_type:
            dom_element.return_type = code_dom.type.DOMType.parse(context, stream)
            if dom_element.return_type is None:
                stream.rewind(checkpoint)
                return None
            dom_element.return_type.parent = dom_element

        # Function name

        name_token = stream.get_token_of_type(["THING"])
        if name_token is None:
            stream.rewind(checkpoint)
            return None
        dom_element.tokens.append(name_token)

        if name_token.value == "operator":
            # If we got "operator" then we need to read the real name from the next tokens too
            # (tokens because of things like "operator[]" and "operator*=")

            operator_name_tokens = []
            while True:
                next_token = stream.get_token()
                if next_token is None:
                    stream.rewind(checkpoint)
                    return None
                if next_token.type == 'LPAREN':
                    #  We found the opening parentheses
                    stream.rewind_one_token()  # Give this back as we want to parse it in a moment
                    break
                else:
                    operator_name_tokens.append(next_token)
            dom_element.is_operator = True

            dom_element.name = "operator " + name_prefix + collapse_tokens_to_string(operator_name_tokens)
        else:
            dom_element.name = name_prefix + name_token.value

        # Arguments

        if stream.get_token_of_type(["LPAREN"]) is None:
            # Not a valid function declaration
            stream.rewind(checkpoint)
            return None

        while True:
            # Check if we've reached the end of the argument list
            if stream.get_token_of_type(['RPAREN']) is not None:
                break

            arg = code_dom.functionargument.DOMFunctionArgument.parse(context, stream)
            if arg is None:
                stream.rewind(checkpoint)
                return None

            dom_element.add_argument(arg)

            # Eat any trailing comma
            stream.get_token_of_type(["COMMA"])

        # Check for function declaration suffix

        if stream.get_token_of_type(['CONST']) is not None:
            dom_element.is_const = True

        # Check for IM_FMTARGS()

        if (stream.peek_token() is not None) and (stream.peek_token().value == 'IM_FMTARGS'):
            stream.get_token()  # Eat token
            if stream.get_token_of_type(['LPAREN']) is None:
                stream.rewind(checkpoint)
                return None
            dom_element.im_fmtargs = stream.get_token().value
            if stream.get_token_of_type(['RPAREN']) is None:
                stream.rewind(checkpoint)
                return None

        # Check for IM_FMTLIST()

        if (stream.peek_token() is not None) and (stream.peek_token().value == 'IM_FMTLIST'):
            stream.get_token()  # Eat token
            if stream.get_token_of_type(['LPAREN']) is None:
                stream.rewind(checkpoint)
                return None
            dom_element.im_fmtlist = stream.get_token().value
            if stream.get_token_of_type(['RPAREN']) is None:
                stream.rewind(checkpoint)
                return None

        # Possible attached comment
        # (this is kinda hacky as there are a bunch of places comments can legitimately be that aren't properly parsed
        # at the moment, but it'll do and this is arguably a valid special case as we want to treat a comment here
        # as attached to the function rather than part of the body)

        attached_comment = stream.get_token_of_type(["LINE_COMMENT", "BLOCK_COMMENT"])
        if attached_comment is not None:
            stream.rewind_one_token()
            dom_element.attached_comment = code_dom.comment.DOMComment.parse(context, stream)
            dom_element.attached_comment.is_attached_comment = True
            dom_element.attached_comment.parent = dom_element

        # Possible initialiser list

        initialiser_list_opener = stream.get_token_of_type(["COLON"])
        if initialiser_list_opener is not None:
            dom_element.initialiser_list_tokens = []
            dom_element.initialiser_list_tokens.append(initialiser_list_opener)

            while True:
                tok = stream.get_token()

                if tok.type == 'LBRACE':
                    # Start of code block
                    stream.rewind_one_token()
                    break
                elif tok.type == 'SEMICOLON':
                    # End of declaration
                    stream.rewind_one_token()
                    break
                else:
                    dom_element.initialiser_list_tokens.append(tok)

        # Possible body

        body_opener = stream.get_token_of_type(["LBRACE", "SEMICOLON"])
        if body_opener is None:
            stream.rewind(checkpoint)
            return None

        if body_opener.type == 'LBRACE':
            stream.rewind_one_token()
            dom_element.body = code_dom.codeblock.DOMCodeBlock.parse(context, stream)

        # print(dom_element)
        return dom_element

    def get_fully_qualified_name(self, leaf_name="", include_leading_colons=False,
                                 return_fqn_even_for_member_functions=False):
        if self.parent is not None:
            # When referring to non-static class member functions we use the leaf name (as the class name is supplied
            # by the instance)
            if (self.get_parent_class() is not None) and not self.is_static and \
                    not return_fqn_even_for_member_functions:
                return self.name
            return self.parent.get_fully_qualified_name(self.name, include_leading_colons)
        else:
            return self.name

    # Add a new argument to this element
    def add_argument(self, child):
        child.parent = self
        self.arguments.append(child)

    # Remove an argument from this element
    def remove_argument(self, child):
        if child.parent is not self:
            raise Exception("Attempt to remove argument from element other than parent")
        self.arguments.remove(child)
        child.parent = None

    def get_child_lists(self):
        lists = code_dom.element.DOMElement.get_child_lists(self)
        lists.append(self.arguments)
        if self.return_type is not None:
            lists.append([self.return_type])
        return lists

    def get_writable_child_lists(self):
        lists = code_dom.element.DOMElement.get_writable_child_lists(self)
        lists.append(self.arguments)
        return lists

    def clone(self):
        # We don't want to clone the original class, but just keep a shallow reference to it
        old_original_class = self.original_class
        self.original_class = None
        clone = code_dom.element.DOMElement.clone(self)
        self.original_class = old_original_class
        clone.original_class = old_original_class
        return clone

    # Get the prefixes and return type for this function
    # This is a separate function largely because mod_align_function_names needs it
    def get_prefixes_and_return_type(self, context=WriteContext()):
        declaration = ""
        if self.is_imgui_api:
            if context.for_c:
                declaration += "CIMGUI_API "  # Use CIMGUI_API instead of IMGUI_API as our define here
            else:
                declaration += "IMGUI_API "
        if self.is_static and (not context.for_implementation):
            declaration += "static "
        if self.is_inline and (not context.for_implementation):
            if context.for_c:
                declaration += "static inline "
            else:
                declaration += "inline "
        if self.return_type is not None:
            declaration += self.return_type.to_c_string(context) + " "
        return declaration

    # Write this element out as C code
    def write_to_c(self, file, indent=0, context=WriteContext()):
        self.write_preceding_comments(file, indent, context)
        declaration = self.get_prefixes_and_return_type(context)

        # Pad declaration to align name
        if len(declaration) < self.function_name_alignment:
            declaration += " " * (self.function_name_alignment - len(declaration))

        if context.for_implementation:
            declaration += str(self.get_fully_qualified_name()) + "("
        else:
            declaration += str(self.name) + "("
        argument_declaration = ""
        if len(self.arguments) > 0:
            first_arg = True
            for arg in self.arguments:
                if arg.is_implicit_default:
                    continue  # Skip anything that is implicitly defaulted
                if not first_arg:
                    argument_declaration += ", "
                argument_declaration += arg.to_c_string(context)
                first_arg = False
        if context.for_c and argument_declaration == "":
            argument_declaration += "void"  # Explicit void for C
        declaration += argument_declaration
        declaration += ")"
        if self.is_const:
            declaration += " const"
        if self.is_constexpr:
            declaration += " constexpr"
        if not context.for_implementation:
            if self.im_fmtargs is not None:
                declaration += " IM_FMTARGS(" + self.im_fmtargs + ")"
            if self.im_fmtlist is not None:
                declaration += " IM_FMTLIST(" + self.im_fmtlist + ")"

        if context.for_implementation:
            write_c_line(file, indent, declaration)
        else:
            if self.body is not None:
                write_c_line(file, indent, self.add_attached_comment_to_line(declaration))
                if self.initialiser_list_tokens is not None:
                    write_c_line(file, indent, collapse_tokens_to_string(self.initialiser_list_tokens))
                self.body.write_to_c(file, indent, context)  # No +1 here because we want the body braces at our level
            else:
                write_c_line(file, indent, self.add_attached_comment_to_line(declaration + ";"))

    def __str__(self):
        result = "Function: Return type=" + str(self.return_type) + " Name=" + str(self.name)
        if len(self.arguments) > 0:
            result += " Arguments="
            for arg in self.arguments:
                result += " [" + str(arg) + "]"
        result += " Body=" + str(self.body)
        if self.is_const:
            result += " Const"
        if self.is_inline:
            result += " Inline"
        if self.is_static:
            result += " Static"
        if self.is_imgui_api:
            result += " IMGUI_API"
        if self.im_fmtargs is not None:
            result += " IM_FMTARGS(" + self.im_fmtargs + ")"
        if self.im_fmtlist is not None:
            result += " IM_FMTLIST(" + self.im_fmtlist + ")"
        return result
