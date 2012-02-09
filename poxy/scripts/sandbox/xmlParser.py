#! /usr/bin/env python
"""
Generate a Python object based on an input XML file
"""

import re
import xml.sax.handler

class xmlObject:
    def __init__(self, config_xml):
        self.config_xml = config_xml
        if not self.file_exists():
            raise RuntimeError('Error opening config file')
        fh = open(self.config_xml, 'r')
        config_str = fh.read()
        self.xmlobj = xml2obj(config_str)

    def file_exists(self):
        try:
            f = open(self.config_xml)
        except IOError:
            exists = False
        else:
            exists = True
            f.close()
        return exists

def xml2obj(src):
    """
    A simple function to converts XML data into native Python object.
    """

    non_id_char = re.compile('[^_0-9a-zA-Z]')
    def _name_mangle(name):
        return non_id_char.sub('_', name)

    class DataNode(object):
        def __init__(self):
            self._attrs = {}    # XML attributes and child elements
            self.data = None    # child text data
        def __len__(self):
            # treat single element as a list of 1
            return 1
        def __getitem__(self, key):
            if isinstance(key, basestring):
                return self._attrs.get(key,None)
            else:
                return [self][key]
        def __contains__(self, name):
            return self._attrs.has_key(name)
        def __nonzero__(self):
            return bool(self._attrs or self.data)
        def __getattr__(self, name):
            if name.startswith('__'):
                # need to do this for Python special methods???
                raise AttributeError(name)
            return self._attrs.get(name,None)
        def _add_xml_attr(self, name, value):
            if name in self._attrs:
                # multiple attribute of the same name are represented by a list
                children = self._attrs[name]
                if not isinstance(children, list):
                    children = [children]
                    self._attrs[name] = children
                children.append(self._cast(value))
            else:
                self._attrs[name] = self._cast(value)
        def __str__(self):
            return self.data or ''
        def __repr__(self):
            items = sorted(self._attrs.items())
            if self.data:
                items.append(('data', self._cast(self.data)))
            return u'{%s}' % ', '.join([u'%s:%s' % (k,repr(v)) for k,v in items])
        def _cast(self, val):
            ''' A method to cast unicode values into ints, floats, strings and True/False,
            based on content'''
            if ((len(str(val))!=0) and (type(val)==unicode)):
                val=str(val)
                #Only attempt to cast things which are values
                #First try and read as an integer
                #Detect the base
                try:
                    if val[0:2] == '0b': base=2
                    elif val[0:2] == '0x': base=16
                    else: base=10
                except:
                    base = 10
                #Try and convert to integer
                try:
                    if base != 10:
                        return int(val[2:],base)
                    else:
                        return int(val)
                except ValueError:
                    # Not an integer
                    pass

                # Integer cast failed -- try and read as a float
                try:
                    return float(val)
                except ValueError:
                    # Not a float
                    pass

                # Float cast failed. Try and read as a string, catching True/False bools
                if ((val == 'True') or (val == 'true')): return True
                elif ((val == 'False') or (val == 'false')): return False
                else: return val
            else:
                # val was not a data value. Leave it alone
                return val


                

    class TreeBuilder(xml.sax.handler.ContentHandler):
        def __init__(self):
            self.stack = []
            self.root = DataNode()
            self.current = self.root
            self.text_parts = []
        def startElement(self, name, attrs):
            self.stack.append((self.current, self.text_parts))
            self.current = DataNode()
            self.text_parts = []
            # xml attributes --> python attributes
            for k, v in attrs.items():
                self.current._add_xml_attr(_name_mangle(k), v)
        def endElement(self, name):
            text = ''.join(self.text_parts).strip()
            if text:
                self.current.data = text
            if self.current._attrs:
                obj = self.current
            else:
                # a text only node is simply represented by the string
                obj = text or ''
            self.current, self.text_parts = self.stack.pop()
            self.current._add_xml_attr(_name_mangle(name), obj)
        def characters(self, content):
            self.text_parts.append(content)

    builder = TreeBuilder()
    if isinstance(src,basestring):
        xml.sax.parseString(src, builder)
    else:
        xml.sax.parse(src, builder)
    return builder.root._attrs.values()[0]

