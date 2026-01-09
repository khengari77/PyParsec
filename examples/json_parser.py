from pyparsec.Language import python_style
from pyparsec.Token import TokenParser
from pyparsec.Prim import run_parser, lazy, pure, try_parse
from pyparsec.Combinators import sep_by

# 1. Lexer Setup
# JSON is very similar to Python style (identifiers, strings, numbers)
lexer = TokenParser(python_style)

# Token Parsers
symbol = lexer.symbol
string_literal = lexer.string_literal
float_literal = lexer.float
int_literal = lexer.integer
# JSON allows "null", "true", "false". We map them to Python equivalents.
null_val = symbol("null") >> pure(None)
true_val = symbol("true") >> pure(True)
false_val = symbol("false") >> pure(False)

# 2. Recursive JSON Parser
def json_value():
    return (
        null_val
        | true_val
        | false_val
        | string_literal
        | try_parse(float_literal)
        | int_literal
        | json_object()
        | json_array()
    )

def json_array():
    # [ value, value, ... ]
    return lexer.brackets(sep_by(lazy(json_value), symbol(",")))

def json_object():
    # { "key": value, ... }
    def entry():
        return string_literal.bind(lambda key: 
               symbol(":") >> 
               lazy(json_value).bind(lambda val: 
               pure((key, val))))

    return lexer.braces(sep_by(entry(), symbol(","))).map(dict)

parser = json_value()

if __name__ == "__main__":
    with open("examples/json_example.json") as f:
        test_json = f.read()
    
    result, err = run_parser(parser, test_json)
    
    if err:
        print("Parsing Failed:", err)
    else:
        import json
        print("Successfully Parsed:")
        print(json.dumps(result, indent=4))
