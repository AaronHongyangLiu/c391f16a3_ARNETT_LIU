import sqlite3  # https://docs.python.org/2/library/sqlite3.html
import sys
import re

"""
TODO:
- regex to remove from "." causes objects with "." in them to be invalid. Example: dbr:Edmonton	georss:point	"53.53333333333333 -113.5" .
- must determine types in line 160
- ignore non @en lines

"""


PREFIX_URL = {}
db = None

STATE = {
    'SAME_SUBJECT': False,
    'SAME_PREDICATE': False,
    'SAME_OBJECT': False
}


def main():
    if len(sys.argv) != 3:
        print "Usage: python q8.py <database file> <RDF input file>"
        sys.exit()

    # db = sqlite3.connect(sys.argv[1])
    # cursor = db.cursor()

    infile = open(sys.argv[2], 'r')  # read the RDF data file
    input_lines = infile.readlines()
    infile.close()

    # parse_file(database, input_lines)
    parse_file(input_lines)

    # db.close()


def parse_file(lines):
    """
    parses lines of the file for insertion to the database
    param db: the database instance
    param lines: the list of lines read from RDF data file
    """

    # initialize statements to false
    subject = None
    predicate = None
    object = None
    type = None

    for line in lines:
        # check if prefix line
        prefix = re.search("(?:)@prefix(.*)", line)  # https://docs.python.org/2/howto/regex.html
        if prefix:
            add_prefix(prefix)
            continue  # go to next line

        line_contents = line.split('\t')

        # generate new triple without any existing context
        if line_contents[0] != '':
            subject, predicate, object, type = get_attributes(line_contents, predicate=None, subject=None)

        # generate triple with existing subject and predicate
        elif line_contents[0] == '' and line_contents[1] == '' and STATE['SAME_SUBJECT'] and STATE['SAME_PREDICATE']:
            subject, predicate, object, type = get_attributes(line_contents, predicate=predicate, subject=subject)

        # genereate triple with existing subject but new predicate
        elif line_contents[0] == '' and line_contents[1] != '' and STATE['SAME_SUBJECT'] and not STATE['SAME_PREDICATE']:
            subject, predicate, object, type = get_attributes(line_contents, predicate=None, subject=subject)

        insert_triple(subject, predicate, object, type)


def get_attributes(line_contents, predicate, subject):
    """
    based on the line being parsed, the appropriate DB ready attributes are generated
    :param line_contents: The array of the tab separated line
    :param predicate: The current predicate resource that applies to the line being parsed. AKA the context of the line
    :param subject: The current subject resource that applies to the line being parsed. AKA the context of the line
    :return: the attributes ready to be inserted into DB
    """
    object = None

    if not subject: # Then new subject being encountered
        subject = get_url_syntax(line_contents[0])
        if not subject: # Then in prefix form
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
        if not object: # Then object is in prefix form
            object_with_prefix = re.search("^[^,]*", line_contents[
                2])
            try:
                object_with_prefix.group(2) # This checks to see if multiple commas found in line
                print ("Invalid data: multiple comma's in line")
                sys.exit(1)
            except IndexError:
                object_with_prefix = object_with_prefix.group()

        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = True

    elif end_line_token == '.':
        object = get_url_syntax(line_contents[2])
        if not object:
            object_with_prefix = re.search("^[^.]*", line_contents[
                2]).group()

        STATE['SAME_SUBJECT'] = False
        STATE['SAME_PREDICATE'] = False

    elif end_line_token == ';':  # new predicate
        object = get_url_syntax(line_contents[2])
        if not object:
            object_with_prefix = re.search("^[^;]*", line_contents[2]).group()
        STATE['SAME_SUBJECT'] = True
        STATE['SAME_PREDICATE'] = False

    else:
        if line_contents[2][-1] == '.': # Then we have the last line in the file
            object = get_url_syntax(line_contents[2])
            if not object:
                object_with_prefix = re.search("^[^.]*", line_contents[
                    2]).group()

            STATE['SAME_SUBJECT'] = False
            STATE['SAME_PREDICATE'] = False
        else:
            print ("invalid identifier at end of line")
            sys.exit(1)


    # handle prefix tags with other data
    if not object:
        if object_with_prefix and ":" in object_with_prefix:
            if("^^" in object_with_prefix):
                object = object_with_prefix
            else:
                object = translate_tag(object_with_prefix)
            type = 'url'
            # TODO here we handle url tags
        else: # Then we do not have a url
            # TODO determine type of object and assign to type for this functions return
            type = 'other'
            object = object_with_prefix

    else:
        type = 'url'

    # if not STATE['SAME_SUBJECT']:
    #     subject = None
    #     predicate = None
    #     object = None
    # if not STATE['SAME_PREDICATE']:
    #     predicate = None
    #     object = None

    return subject, predicate, object, type


def get_url_syntax(object):
    """
    determines if object is given in prefix form or url form. If in url form it returns the url, othewise returns None
    :return: objects url if input is url form, otherwise None
    """
    if "<" in object and ">" in object:
        return object[object.find("<") + 1:object.find(">")]

    return None



def translate_tag(tag):
    """
    generates the text that will be saved in database
    :param tag: example -->  dbr:Edmonton
    :return: the tag without prefixes
    """
    tag_contents = tag.split(':')
    if tag_contents[0] == "_": # then blank node
        return tag_contents[1]

    result = "%s%s" % (PREFIX_URL[tag_contents[0]], tag_contents[1])
    return result


def add_prefix(prefix):
    prefix_contents = prefix.group(1).split('\t')

    # this gets the url of the prefix tag. http://stackoverflow.com/questions/4894069/regular-expression-to-return-text-between-parenthesis
    url = prefix_contents[1][prefix_contents[1].find("<") + 1:prefix_contents[1].find(
        ">")]

    PREFIX_URL[prefix_contents[0].strip()[:-1]] = url  # Add to the PREFIX_URL dictionary


def insert_triple(subject, predicate, object, type):
    print '\n'

    print subject
    print predicate
    print object
    print '\n'

    # TODO insert into the DB
    return


# def new_triple():
#     """
#     :return: true if not currently parsing a previous triple
#     """
#     return (not STATE['IN_OBJECT'] and not STATE['IN_PREDICATE'] and not STATE['IN_SUBJECT'])

if __name__ == "__main__":
    main()
