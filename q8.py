import sqlite3  # https://docs.python.org/2/library/sqlite3.html
import sys
import re


"""
TODO implement a better way to insert into DB. Insert every 1000 rows or so, but then delete all data if an error occurs
"""
PREFIX_URL = {}
DB_DATA = []

STATE = {
    'SAME_SUBJECT': False,
    'SAME_PREDICATE': False,
    'SAME_OBJECT': False
}

END_LINE_TOKENS = ['.', ',', ';']


def main():
    if len(sys.argv) != 3:
        print "Usage: python q8.py <database file> <RDF input file>"
        sys.exit()

    db = sqlite3.connect(sys.argv[1])
    db.text_factory = str
    infile = open(sys.argv[2], 'r')  # read the RDF data file
    input_lines = infile.readlines()
    infile.close()

    parse_file(input_lines)

    insert_data(db)
    db.close()


def parse_file(lines):
    """
    parses lines of the file for insertion to the database
    param lines: the list of lines read from RDF data file
    """

    # Initialization
    subject = None
    predicate = None
    object = None
    obj_type = None

    for line in lines:
        if '#' in line and "<" not in line and ">" not in line:  # Then comment exists and we ignore
            # we check for presence of "<" and ">" because '#'s can be found in urls,
            # and urls are encased in '<' and '>'
            index = line.find('#')
            line = line[:index].rstrip()
            line += '\n'  # add newline character to keep format consistent

        if line == "\n":  # Ignore blank lines
            continue

        if line.strip('\n')[-1] not in END_LINE_TOKENS:
            print "There is a line missing a valid end-line token. '%s' not in %s" % (
                line.strip('\n')[-1], END_LINE_TOKENS)
            sys.exit(1)
        # check if @prefix line
        prefix = re.search("(?:)@prefix(.*)", line)  # https://docs.python.org/2/howto/regex.html
        if prefix:
            add_prefix(prefix)
            continue  # go to next line

        line_contents = line.split('\t')

        # generate new triple without any existing context
        if line_contents[0] != '':
            subject, predicate, object, obj_type, numerical_object = get_attributes(line_contents, predicate=None, subject=None)

        # generate triple with existing subject and predicate
        elif line_contents[0] == '' and line_contents[1] == '' and STATE['SAME_SUBJECT'] and STATE['SAME_PREDICATE']:
            subject, predicate, object, obj_type, numerical_object = get_attributes(line_contents, predicate=predicate, subject=subject)

        # generate triple with existing subject but new predicate
        elif line_contents[0] == '' and line_contents[1] != '' and STATE['SAME_SUBJECT'] and not STATE[
            'SAME_PREDICATE']:
            subject, predicate, object, obj_type, numerical_object = get_attributes(line_contents, predicate=None, subject=subject)

        else:
            print "Syntax error - Invalid use of end-line token (expected a different end line token than the one given). \nRefer to line containing '%s'" % (
                '\t').join(line_contents).strip('\n')
            sys.exit(1)

        object = is_english(object)  # returns english object, or None if not english
        if object:
            DB_DATA.append((subject, predicate, object, obj_type, numerical_object))

    return


def get_attributes(line_contents, predicate, subject):
    """
    based on the line being parsed, the appropriate DB ready attributes are generated
    :param line_contents: The array of the tab separated line
    :param predicate: The current predicate resource that applies to the line being parsed. AKA the context of the line
    :param subject: The current subject resource that applies to the line being parsed. AKA the context of the line
    :return: the attributes ready to be inserted into DB
    """
    object = None

    if not subject:  # Then new subject being encountered
        subject = get_url_syntax(line_contents[0])
        if not subject:  # Then in prefix form
            subject = translate_tag(line_contents[0])
        STATE['SAME_SUBJECT'] = True

        predicate = get_url_syntax(line_contents[1])
        if not predicate:
            predicate = translate_tag(line_contents[1])

    if subject and not predicate:
        predicate = get_url_syntax(line_contents[1])
        if not predicate:
            predicate = translate_tag(line_contents[1])

    end_line_token = line_contents[2][-2]  # -2 index because last character is newline character

    if end_line_token == ',':  # new object under same predicate and subject
        object = get_url_syntax(line_contents[2])
        if not object:  # Then object is in prefix form
            object_with_prefix = strip_end_line(line_contents[2], token=',')

        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = True

    elif end_line_token == '.':
        object = get_url_syntax(line_contents[2])
        if not object:
            object_with_prefix = strip_end_line(line_contents[2], token='.')

        STATE['SAME_SUBJECT'] = False
        STATE['SAME_PREDICATE'] = False

    elif end_line_token == ';':  # new predicate
        object = get_url_syntax(line_contents[2])
        if not object:
            object_with_prefix = strip_end_line(line_contents[2], token=';')

        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = False

    else:
        if line_contents[2][-1] == '.':  # Then we have the last line in the file
            object = get_url_syntax(line_contents[2])
            if not object:
                object_with_prefix = re.search("^[^.]*", line_contents[
                    2]).group()

            STATE['SAME_SUBJECT'] = False
            STATE['SAME_PREDICATE'] = False
        else:
            print ("invalid or missing identifier at end of line")
            sys.exit(1)

    # handle prefix tags with other data
    if not object:
        if ":" in object_with_prefix and "^^" not in object_with_prefix:
            object = translate_tag(object_with_prefix)

        else:  # Then we do not have a url
            object = object_with_prefix

    object, obj_type, numerical_object = determine_type(object)

    return subject, predicate, object, obj_type, numerical_object


def strip_end_line(object, token):
    """
    strips the trailing token from a line
    from: http://stackoverflow.com/questions/4664850/find-all-occurrences-of-a-substring-in-python
    :param object: object string for object to be stripped
    :param token: the character token to be stripped
    :return: trimmed object
    """
    last_instance_index = [m.start() for m in re.finditer(token, object)][-1]
    if object[last_instance_index - 1] == ' ' and object[last_instance_index + 1] == '\n':
        object = object[:last_instance_index].strip()
    else:
        print "invalid line ending"
        sys.exit(1)

    return object


def determine_type(object):
    """
    determines the object's type. If the object contains a prefix then the obj_type will be a url describing object type
    and the object will be the string before the tag was included.
    example:
        if input is "812201"^^xsd:nonNegativeInteger
        then result will be:
            object = "812201"
            object_type = http://www.w3.org/2001/XMLSchema#nonNegativeInteger
    :param object: the object whose type is to be determined
    :return: object in string representation, a tag of it's type, and a numeric representation of the float/int type objects (otherwise None for string type objects)
    """
    object_type = 'other'  # 'other' by default
    numerical_object = None

    try:
        if "." in object:
            numerical_object = float(object)
            object_type = 'float'
        else:
            numerical_object = int(object)
            object_type = 'int'

    except ValueError:
        if "http://" in object:
            object_type = 'url'
        else:
            object_type = "literal"

        if "^^" in object:
            object_contents = object.split("^^")
            object = object_contents[0]
            object_type = translate_tag(object_contents[1])

            numerical_object = None

    return object, object_type, numerical_object


def get_url_syntax(object):
    """
    determines if object is given in prefix form or url form. If in url form it returns the url, otherwise returns None
    :return: objects url if input is url form, otherwise None
    """
    if "<" in object and ">" in object:
        return object[object.find("<") + 1:object.find(">")]

    return None


def translate_tag(tag):
    """
    generates the text that will be saved in database
    WARNING - blank nodes are stored as they come. _:b27527865 ---> _:b27527865
    :param tag: example -->  dbr:Edmonton
    :return: the tag without prefixes ---> 'http://dbpedia.org/resource/Edmonton'
    """
    if ":" not in tag:
        print "Invalid character found in input. Line contents = '%s'" % tag.strip('\n')
        sys.exit(1)
    tag_contents = tag.split(':')
    if tag_contents[0] == "_":
        return tag.strip()

    if tag_contents[0] not in PREFIX_URL.keys():
        print "prefix tag '%s' is undefined in input file." % tag_contents[0]
        sys.exit(1)

    result = "%s%s" % (PREFIX_URL[tag_contents[0]], tag_contents[1])
    return result


def add_prefix(prefix):
    """
    given a string with a prefix (ex. rdf:	<http://www.w3.org/1999/02/22-rdf-syntax-ns#> this function
    will add the key/value pair (key = rdf, value = http://www.w3.org/1999/02/22-rdf-syntax-ns#) to the PREFIX_URL
    dictionary
    """
    prefix_contents = prefix.group(1).split('\t')
    if len(prefix_contents) != 2:
        print "Invalid prefix tag in input file"
        sys.exit(1)

    # this gets the url of the prefix tag. http://stackoverflow.com/questions/4894069/regular-expression-to-return-text-between-parenthesis
    url = prefix_contents[1][prefix_contents[1].find("<") + 1:prefix_contents[1].find(
        ">")]

    PREFIX_URL[prefix_contents[0].strip()[:-1]] = url  # Add to the PREFIX_URL dictionary


def insert_data(db):
    """
    function that inserts the data to DB.
    One bulk DB insert for efficiency. and only after checking there are no errors

    from: https://docs.python.org/2/library/sqlite3.html
    :param db: database instance
    """

    cursor = db.cursor()
    if cursor:
        for triple in DB_DATA:
            print triple
        print len(DB_DATA)
        # cursor.executemany('INSERT INTO graph_data VALUES (?,?,?,?,?)', DB_DATA)
        # db.commit()

    return


def is_english(object):
    """
    determines if the input attributes are english or not and removes language tag if found
    :param object: the term to check for english qualities
    :return: object ready for
    """

    language_tag = re.search("@[a-z]*", object)
    if language_tag:
        if language_tag.group() != "@en":
            return None  # Was another language
        else:
            object = object.replace("@en", '')

    return object


if __name__ == "__main__":
    main()
