from __future__ import print_function
import sqlite3
import sys

PREFIX = {}
OUTPUT_VAR = []
STATE = {'IN_PREFIX': False,
         'IN_SELECT': False,
         'IN_WHERE': False,
         'IN_FILTER': False}
SUB_QUERIES = []
SUB_VARS = []
FILTERS = []
FILTER_VAR = []


def main():
    if len(sys.argv) != 3:
        print("Usage: python q9.py <database file> <SPARQL query file>")
        sys.exit()

    infile = open(sys.argv[2], 'r')  # read the SPARQL query file
    whole_file = infile.read()
    infile.close()

    input_lines = reformat(whole_file)
    query = parseFile(input_lines)

    #print(query)

    conn = sqlite3.connect(sys.argv[1])  # connection to the database
    c = conn.cursor()  # cursor
    conn.create_function("convert",1,convert)
    c.execute(query)
    result = c.fetchall()

    for i in range(len(OUTPUT_VAR)):
        if i != (len(OUTPUT_VAR)-1):
            print("{:_^51}".format(OUTPUT_VAR[i]),end="")
        else:
            print("{:_^51}".format(OUTPUT_VAR[i]))

    for rows in result:
        for i in range(len(OUTPUT_VAR)):
            if i != (len(OUTPUT_VAR)-1):
                print("|%-50s" % rows[i], end="")
            else:
                print("|%-50s|"  % rows[i])
    conn.close()


def convert(value):
    """
    this is a sql function that will try to convert value to int or float
    :param value: value of the object column that returned by a query
    :return: the converted value
    """
    try:
        if "." in value:
            a = float(value)
        else:
            a = int(value)

        return a
    except ValueError:
        return value


def reformat(string):
    """
    change the format of file so that:
      1. "SELECT" and "WHERE" will be in different lines
      2. (subj pred obj) and "WHERE {" will be in different lines
      3. there will be at least one space between SELECT and first ?var or *
      4. there will be at least one space between WHERE and {
      5. there will be at least one space between FILTER and (
    :param string: all the characters in the input file
    :return: a list of each line in the formatted file
    """

    # changes #3
    select_index = string.upper().index("\nSELECT") + 6
    string = string[:select_index + 1] + " " + string[select_index + 1:]

    # changes #1,#2,#4
    where_index = 0
    while where_index < select_index:
        where_index = string.upper().find("WHERE", where_index + 1) + 4
    curly_open = string.find("{", where_index + 1)
    string = string[:where_index - 4] + "\nWHERE {" + string[curly_open + 1:]

    # changes #5
    filter_index = string.upper().find("FILTER", 0)
    while filter_index >= 0:
        string = string[:filter_index + 6] + " " + string[filter_index + 6:]
        filter_index = string.upper().find("FILTER", filter_index + 1)

    return string.split("\n")


def parseFile(sparql_lines):
    """
    parse the SPARQL query, translate and return it as an sqlite query
    :param sparql_lines: a list of each line in the SPARQL query file
    :return: a string containing sqlite query
    """
    for line in sparql_lines:
        line = line.strip()
        if line == "":  # if the line is blank, go to next line
            continue
        line = line.split()

        if line[0].upper() == "PREFIX":
            STATE['IN_PREFIX'] = True
            if len(line) == 3:  # if there are spaces between ':' and <url>
                PREFIX[line[1][:-1]] = line[2][1:-1]
            elif len(line) == 2:  # if there's no space:
                index_of_colon = line[1].index(":")
                PREFIX[line[1][:index_of_colon]] = line[1][index_of_colon + 2:-1]
            else:
                print("Unexpected error when reading prefix line with tokens:", line)
                sys.exit()

        elif line[0].upper() == "SELECT":
            STATE['IN_PREFIX'] = False
            STATE['IN_SELECT'] = True
            for token in line:
                if token.upper() == "SELECT":
                    continue
                elif "*" in token:
                    OUTPUT_VAR.append("*")
                    break
                elif "?" in token:
                    OUTPUT_VAR.append(token[1:])  # add the ?var into the outputVar list
                else:
                    print("Unexpected error when reading ?var in SELECT line with tokens:", line, "token:", token)
                    sys.exit()

        elif line[0].upper() == "WHERE":
            STATE['IN_SELECT'] = False
            STATE['IN_WHERE'] = True

        elif STATE['IN_WHERE']:
            if line[0][:6].upper() == "FILTER":  # if this is a filter line
                addFilter(line[1:])
            elif line[0] == "}":
                STATE['IN_WHERE'] = False
            else:
                readPattern(line)

        else:
            print("Unexpected error while parsing line with tokens:", line)
            sys.exit()

    result = buildQuery()
    return result


def addFilter(tokens):
    """
    add the filter line to the global variable
    :param tokens: all the token in the filter line
    """
    
    filter_line = join_literal(tokens)
    filter_line = "".join(filter_line)
    variable_start = filter_line.find("?")
    var_name = ""
    variable_end = variable_start
    for char in filter_line[variable_start + 1:]:
        if char not in ",><=)":
            var_name += char
            variable_end += 1
        else:
            break
    FILTER_VAR.append(var_name)
    if "REGEX" in filter_line.upper():

        first_quote = filter_line.find('''"''')
        if first_quote > 0:
            second_quote = filter_line.find('''"''', first_quote + 1)
        else:
            first_quote = filter_line.find("'")
            if first_quote < 0:
                print("error")
                sys.exit()
            second_quote = filter_line.find("'", first_quote + 1)
        target_string = filter_line[first_quote + 1:second_quote]

        FILTERS.append("""%s = '"%s"'""" % (var_name, target_string))
    else:
        # it has to be a number
        filter_line = filter_line[:variable_start + 1] + filter_line[variable_end + 1:]
        number = ""
        operation = ""
        for char in filter_line:
            if char.isdigit() or char == ".":
                number += char

        operations = ["!=", ">=", "<=", "=", ">", "<"]
        for op in operations:
            if op in filter_line:
                operation = op
                break
        filter_line.find("!")
        FILTERS.append("%s %s %s and (%s_type=='int' or %s_type=='float') " % (var_name, operation, number,var_name,var_name))


def readPattern(pattern):
    """
    read a (subj pred obej) pattern, store the variable and sub-sql-query in the dictionary
    :param pattern: a list as [subj, pred, obej] pattern
    """

    query_template = {(0,): ("subject as %s ", '''predicate = "%s" and object = "%s"''', "predicate_object_index"),
                      (1,): ("predicate as %s ", '''subject = "%s" and object = "%s"''', "subject_object_index"),
                      (2,): (
                      "convert(object) as %s , type as %s_type ", '''subject = "%s" and predicate = "%s"''', "subject_predicate_index"),
                      (0, 1): ("subject as %s , predicate as %s ", '''object = "%s"''', "object_index"),
                      (0, 2): ("subject as %s , convert(object) as %s , type as %s_type ", '''predicate = "%s"''', "predicate_index"),
                      (1, 2): ("predicate as %s , convert(object) as %s , type as %s_type ", '''subject = "%s"''', "subject_index"),
                      (0, 1, 2): "subject as %s ,predicate as %s , convert(object) as %s , type as %s_type "}
                      

    if pattern[2][-1] == ".":
        pattern[2] = pattern[2][:-1]

    variables = []
    conditions = []
    template_number = []

    for i in range(3):
        if pattern[i][0] == "?":  # if the term is a variable
            variables.append(pattern[i][1:])
            template_number.append(i)
        elif pattern[i][0] == "<":  # if the term is a url
            conditions.append(pattern[i][1:-1])
        elif ":" in pattern[i]:  # if it's a url with prefix
            index = pattern[i].index(":")
            if pattern[i][:index] not in PREFIX:
                print("Unknown prefix: ", pattern[i])
                sys.exit()
            url = PREFIX[pattern[i][:index]] + pattern[i][index + 1:]
            conditions.append(url)
        else:
            conditions.append(pattern[i])
    template_number = tuple(template_number)

    inputVar = []
    inputVar.extend(variables)
    if 2 in template_number:
        inputVar.append(variables[-1])
    
    if template_number != (0,1,2):
        query = "SELECT DISTINCT %s \nFROM graph_data INDEXED BY %s \nWHERE %s " \
                % (query_template[template_number][0] % tuple(inputVar),
                   query_template[template_number][2],
                   query_template[template_number][1] % tuple(conditions))
    else:
        query = "SELECT DISTINCT %s \nFROM graph_data" % (query_template[template_number] % tuple(inputVar))
    SUB_VARS.append(variables)
    SUB_QUERIES.append(query)


def buildQuery():
    """
    use the global variables to construct a final query
    :return: the final sql query
    """
    keys = SUB_VARS
    current_vars = set(keys.pop(0))
    # combine all the sub-queries:
    query = SUB_QUERIES.pop(0)
    used = []
    while len(used) != len(keys):
        for i in range(len(keys)):
            variables = keys[i]
            if not current_vars.isdisjoint(set(variables)):
                #common_vars = tuple(current_vars.intersection(set(variables)))
                current_vars = current_vars.union(set(variables))
                query = "SELECT * \nFROM (\n(%s) \nNATURAL JOIN \n(%s) )\n " % (query, SUB_QUERIES[i])
                #query += "%s," * (len(common_vars) - 1)
                #query += "%s)\n" % common_vars

                used.append(i)

    # output those needed:
    if OUTPUT_VAR != ["*"]:
        s = "%s, " * (len(OUTPUT_VAR) - 1)
        s += "%s "
        query = ("SELECT %s" % s) % tuple(OUTPUT_VAR) + "\nFROM ( " + query + ")"

        # check error for selected vars
        if not current_vars.issuperset(set(OUTPUT_VAR)):
            print("At least one of the output var is not in the where clause, out:", OUTPUT_VAR, "where:", current_vars)
            sys.exit(1)
    else:
        OUTPUT_VAR.pop()
        OUTPUT_VAR.extend(current_vars)

    if len(FILTERS) != 0:
        # check error in the filter
        if not current_vars.issuperset(set(FILTER_VAR)):
            print("At least one of the filter var is not in the where clause, filter:", FILTER_VAR, "we have:", current_vars)
            sys.exit(1)

        query += " \nWHERE "
        for i in range(len(FILTERS)):
            if i == 0:
                query += FILTERS[i]
            else:
                query += " \nand " + FILTERS[i]

    query += ";"
    return query

def join_literal(line_contents):
    """
    There are likely spaces in the literals given in RDF data, but since we split the lines by spaces
    the literal will be broken up. This method joins the literal back together.
    :param line_contents: the space separated line in array form
    :return: the line contents with literals joined at the spaces
    """
    start_index = None
    end_index = None
    for i in range(len(line_contents)):
        if '"' in line_contents[i] and line_contents[i].count('"') == 1:
            if start_index == None and end_index == None:
                start_index = i
            elif start_index != None and end_index == None:
                end_index = i

    if start_index == None and end_index == None:
        return line_contents

    obj = ''
    for j in range(start_index, end_index + 1):
        obj += '%s ' % line_contents[j]

    array_result = []
    for k in range(len(line_contents)):
        if k < start_index:
            array_result.append(line_contents[k])
        elif k == start_index:
            array_result.append(obj.strip())
        elif start_index < k <= end_index:
            continue
        else:
            array_result.append(line_contents[k])

    return array_result

if __name__ == "__main__":
    main()
