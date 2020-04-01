"""
CLI script to generate Protocol types
"""
import asyncio

import json
import logging
import re
import time
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, Hashable, Match, List, Union, Literal

import networkx as nx

from pyppeteer import launch

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[{levelname}] {name}: {message}', style='{'))
logging.getLogger('pyppeteer').addHandler(handler)

logger = logging.getLogger('CLI')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
handler.setLevel(logging.INFO)


class ProtocolTypesGenerator:
    _forward_ref_re = r'\'Protocol\.(\w+\.\w+)\''
    js_to_py_types = {
        'any': 'Any',
        'string': 'str',
        'object': 'Dict[str, str]',
        'boolean': 'bool',
        'number': 'float',
        'integer': 'int',
        'binary': 'bytes',
    }

    def __init__(self):
        self.td_references = set()
        self.domains = []
        # cache of all known types
        self.all_known_types = {}
        self.typed_dicts = {}
        # store all references from one TypedDict to another
        self.code_gen = TypingCodeGenerator()

    def _resolve_forward_ref_re_sub_repl(self, match: Match, fw_ref: bool) -> str:
        domain_, ref = match.group(1).split('.')
        resolved_fwref = self.all_known_types[domain_][ref]

        # resolve nested forward references
        if re.search(self._forward_ref_re, resolved_fwref):
            resolved_fwref = self.resolve_forward_ref_on_line(resolved_fwref)
        if (
            fw_ref
            and resolved_fwref not in self.js_to_py_types.values()
            and not resolved_fwref.startswith('Literal')
            and not resolved_fwref.startswith('List')
        ):
            # forward ref to a typed dict, not sure that it will be defined
            resolved_fwref = f'\'{resolved_fwref}\''

        return resolved_fwref

    def resolve_forward_ref_on_line(self, line: str, fw_ref: bool = True) -> str:
        """
        Replaces a forward reference in the form 'Protocol.domain.ref' to the actual value of Protocol.domain.ref
        :param line: line in which protocol forward reference occurs.
        :param fw_ref: whether or not to forward reference the resolved reference
        :return: line with resolved forward reference
        """
        # PyCharm can't handle partial
        # noinspection PyTypeChecker
        return re.sub(self._forward_ref_re, partial(self._resolve_forward_ref_re_sub_repl, fw_ref=fw_ref), line)

    async def _retrieve_top_level_domain(self):
        browser = await launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
        base_endpoint = re.search(r'ws://([0-9A-Za-z:.]*)/', browser.wsEndpoint).group(1)
        page = await browser.newPage()

        logger.info(f'Loading raw protocol specification')
        t_start = time.perf_counter()

        await page.goto(f'http://{base_endpoint}/json/protocol')
        page_content = await page.evaluate('document.documentElement.innerText')
        try:
            await browser.close()
        except Exception as e:
            logger.warning(f'Exception on browser close: {e}')

        logger.info(f'Loading raw protocol specification in {time.perf_counter()-t_start:.2f}s')
        self.domain = json.loads(page_content)

    def retrieve_top_level_domain(self):
        """
        Fetches and data, parses it, and sets the class variable 'domains' to it for later use.
        :return: None
        """
        asyncio.get_event_loop().run_until_complete(self._retrieve_top_level_domain())

    def gen_spec(self):
        """
        Generate the Protocol class file lines within self.code_gen attribute. Uses an IndentManager context manager to 
        keep track of the current indentation level. Resolves all forward references. Expands recursive types to an
        approximation of the cyclic type referenced.

        :return: None
        """

        self.generate_header_doc_string()

        logger.info(f'Generating protocol spec')
        t_start = time.perf_counter()

        self.code_gen.add('class Protocol:')
        with self.code_gen.indent_manager:
            for domain in self.domain['domains']:
                domain_name = domain['domain']
                self.code_gen.add(f'class {domain_name}:')
                self.code_gen.add_comment_from_info(domain)
                self.all_known_types[domain_name] = {}
                with self.code_gen.indent_manager:
                    for type_info in domain.get('types', []):
                        self.add_type_item(type_info, 'id', 'properties', domain_name)

                    for payload in domain.get('events', []):
                        payload["name"] = payload["name"] + 'Payload'
                        self.add_type_item(payload, 'name', 'parameters', domain_name, type_conversion_fallback='None')

                    for command_info in domain.get('commands', []):
                        for td_key, suffix in (('properties', 'Parameters'), ('returns', 'ReturnValues')):
                            command_info['name'] = re.subn(r'(Parameters$|$)', suffix, command_info['name'], 1)[0]
                            self.add_type_item(command_info, 'name', td_key, domain_name, type_conversion_fallback='None')

            self.generate_overview()
            self.resolve_all_fw_refs()

        self.expand_recursive_references()
        self.typed_dicts = {k: v for k, v in sorted(self.typed_dicts.items(), key=lambda x: x[0])}
        # all typed dicts are inserted prior to the main Protocol class
        for index, td in enumerate(self.typed_dicts.values()):
            td.add_newlines(num=2)
            self.code_gen.insert_before_code(td)

        logger.info(f'Generated protocol spec in {time.perf_counter() - t_start:.2f}s')
        # newline at end of file
        self.code_gen.add_newlines(num=1)

    def generate_header_doc_string(self):
        """
        Generates a headers doc string for the top of the file.
        :return: None
        """
        self.code_gen.insert_before_code('"""')
        self.code_gen.insert_before_code(f'''\
            Automatically generated by ./{Path(__file__).relative_to(Path(__file__).parents[1]).as_posix()}
            Attention! This file should *not* be modified directly! Instead, use the script to update it. 
    
            Last regeneration: {datetime.utcnow()}''')
        self.code_gen.insert_before_code('"""')
        self.code_gen.add_newlines_before_code(num=2)

    def resolve_all_fw_refs(self):
        # no need for copying list as we aren't adding/removing elements
        # resolve forward refs in main protocol class
        for index, line in enumerate(self.code_gen.code_lines):
            # skip empty lines or lines positively without forward reference
            if not line.strip() or 'Protocol' not in line:
                continue
            self.code_gen.code_lines[index] = self.resolve_forward_ref_on_line(line, fw_ref=False)
        # resolve forward refs in typed dicts, and store instances where s TypedDict references another
        for td_name, td in self.typed_dicts.items():
            for index, line in enumerate(td.code_lines):
                resolved_fw_ref = self.resolve_forward_ref_on_line(line)
                resolved_fw_ref_splits = resolved_fw_ref.split(': ')
                if len(resolved_fw_ref_splits) == 2:  # only pay attention to actual resolve fw refs
                    ref = resolved_fw_ref_splits[1]
                    td_ref_re = r'^(?:List\[)?\'(\w+)\'\]?'
                    if re.search(td_ref_re, ref):
                        self.td_references.add((td_name, re.search(td_ref_re, ref).group(1)))

                self.typed_dicts[td_name].code_lines[index] = resolved_fw_ref

    def generate_overview(self):
        """
        Generate several convenience overview classes, listed in overview_info
        :return: None
        """
        overview_info = {
            'Events': ('events', '\'Protocol.{domain}.{item_name}\''),
            'CommandParameters': ('commands', '\'Protocol.{domain}.{item_name}\''),
            'CommandReturnValues': ('commands', '\'Protocol.{domain}.{item_name}\''),
            'CommandNames': ('commands', '\'{domain}.{item_name}\''),
        }
        last_overview_class = [*overview_info.keys()][0]
        for overview_class, (domain_key, item_fmt) in overview_info.items():
            overview_code_gen = TypingCodeGenerator(init_imports=False)
            overview_code_gen.add(f'class {overview_class}:')
            with overview_code_gen.indent_manager:
                for domain in self.domain['domains']:
                    if domain_key in domain:
                        overview_code_gen.add(f'class {domain["domain"]}:')
                        with overview_code_gen.indent_manager:
                            for item in domain[domain_key]:
                                formatted_name = item_fmt.format(domain=domain['domain'], item_name=item['name'])
                                overview_code_gen.add(f'{item["name"]} = {formatted_name}')
                        overview_code_gen.add_newlines(num=2)
            if overview_class != last_overview_class:
                # don't add newlines to EOF
                overview_code_gen.add_newlines(num=2)
            self.code_gen.add(lines=overview_code_gen.code_lines)

    def add_type_item(
        self,
        type_info,
        type_name_key,
        td_key,
        domain_name,
        type_conversion_fallback: Union[str, Literal[False]] = False,
    ):
        """
        Adds a class attr based on type_info, type_name_key, td_key, domain_name, and type_conversion_fallback

        :param type_info: Dict containing info pertaining to the type
        :param type_name_key: Key to the name of the type
        :param td_key: Key to the item which contains TypedDict info
        :param domain_name: Name of domain
        :param type_conversion_fallback: If not false, used when the type cannot be determined from type_info
        :return: None
        """
        self.code_gen.add_comment_from_info(type_info)
        item_name = type_info[type_name_key]
        if td_key in type_info:
            # item_name = type_info[type_name_key] = '{type_info[type_name_key]}'
            td = self.generate_typed_dict(type_info, domain_name)
            self.typed_dicts.update(td)
            _type = [*td.keys()][0]
        else:
            try:
                _type = self.convert_js_to_py_type(type_info, domain_name)
            except KeyError:
                if type_conversion_fallback is not False:
                    _type = type_conversion_fallback
                else:
                    raise
        self.all_known_types[domain_name][item_name] = _type
        self.code_gen.add(f'{item_name} = {_type}')

    def expand_recursive_references(self):
        """
        Expands recursive references to TypedDicts with Dict[str, Union[Dict[str, Any], str, bool, int, float, List]],
        and adds a comment with the actual type reference.
        :return: None
        """
        for recursive_refs in nx.simple_cycles(nx.DiGraph([*self.td_references])):
            any_recursive_ref = rf'(?:{"|".join(recursive_refs)})'
            expansion = 'Dict[str, Union[Dict[str, Any], str, bool, int, float, List]]'
            for recursing_itm in recursive_refs:
                self.typed_dicts[recursing_itm].filter_lines(
                    sub_pattern_replacements=(
                        (rf'(\s+)(\w+): [\w\[]*?\'({any_recursive_ref})\'\]?', rf'\1# actual: \3\n\1\2: {expansion}\n'),
                    )
                )

    def write_generated_code(self, path: Path = Path('protocol.py')) -> None:
        """
        Write generated code lines to the specified path. Writes to a temporary file and checks that file with mypy to
        'resolve' any cyclic references.

        :param path: path to write type code to.
        :return: None
        """
        if path.is_dir():
            path /= 'protocol.py'
        logger.info(f'Writing generated protocol code to {path}')
        # PyCharm can't handle this path type properly
        # noinspection PyTypeChecker
        with open(path, 'w') as p:
            p.write(str(self.code_gen))

    def generate_typed_dict(self, type_info: Dict[str, Any], domain_name: str) -> Dict[str, 'TypedDictGenerator']:
        """
        Generates TypedDicts based on type_info.

        :param type_info: Dict containing the info for the TypedDict
        :param domain_name: path to resolve relative forward references in type_info against
        :param name: (Optional) Name of TypedDict. Defaults to name found in type_info
        :return: TypedDict corresponding to type information found in type_info
        """
        items = self._multi_fallback_get(type_info, 'returns', 'parameters', 'properties')
        td_name = self._multi_fallback_get(type_info, 'id', 'name')
        is_total = any(1 for x in items if x.get('optional'))
        td = TypedDictGenerator(td_name, is_total)
        with td.indent_manager:
            for item in items:
                td.add_comment_from_info(item)
                _type = self.convert_js_to_py_type(item, domain_name)
                td.add(f'{item["name"]}: {_type}')

        return {td_name: td}

    @staticmethod
    def _multi_fallback_get(d: Dict[Hashable, Any], *k: Hashable):
        """
        Convenience method to retrieve item from dict with multiple keys as fallbacks for failed accesses
        :param d: Dict to retrieve values from
        :param k: keys of Dict to retrieve values from
        :return: first found value where key in k
        """
        for key in k:
            if key in d:
                return d[key]

        raise KeyError(f'{", ".join([str(s) for s in k])} all not found in {d}')

    def convert_js_to_py_type(self, item_info: Union[Dict[str, Any], str], domain_name) -> str:
        """
        Generates a valid python type from the JS type. In the case of type_info being a str, we simply return the
        matching python type from self.js_to_py_types. Otherwise, in the case of type_info being a Dict, we know that
        it will contain vital information about the type we are trying to convert.

        The domain_name is used to qualify relative forward reference in type_info. For example, if
        type_info['$ref'] == 'foo', domain_name would be used produce an absolute forward reference, ie domain_name.foo

        :param item_info: Dict or str containing type_info
        :param domain_name: path to resolve relative forward references in type_info against
        :return: valid python type, either in the form of an absolute forward reference (eg Protocol.bar.foo) or
            primitive type (eg int, float, str, etc)
        """
        if isinstance(item_info, str):
            _type = self.js_to_py_types[item_info]
        elif 'items' in item_info:
            assert item_info['type'] == 'array'
            if '$ref' in item_info['items']:
                ref = item_info['items']['$ref']
                _type = f'List[{self.get_forward_ref(ref, domain_name)}]'
            else:
                _type = f'List[{self.convert_js_to_py_type(item_info["items"]["type"], domain_name)}]'
        else:
            if '$ref' in item_info:
                _type = self.get_forward_ref(item_info['$ref'], domain_name)
            else:
                if 'enum' in item_info:
                    _enum_vals = ', '.join([f'\'{x}\'' for x in item_info['enum']])
                    _type = f'Literal[{_enum_vals}]'
                else:
                    _type = self.js_to_py_types[item_info['type']]

        return _type

    @staticmethod
    def get_forward_ref(relative_ref: str, potential_domain_context: str):
        """
        Generates a forward absolute forward reference to Protocol class attr. If the reference is relative
        to a nested class, the full path is resolved against potential_domain_context. In the case of
        the reference being relative to the Protocol class, the path is simple resolved against the Protocol class

        :param relative_ref: reference to another class, in the form of foo or foo.bar
        :param potential_domain_context: context to resolve class against if relative_ref is relative to it
        :return: absolute forward reference to nested class attr
        """
        if len(relative_ref.split('.')) == 2:
            non_fw_ref = f'Protocol.{relative_ref}'
        else:
            non_fw_ref = f'Protocol.{potential_domain_context}.{relative_ref}'
        return f'\'{non_fw_ref}\''


class TypingCodeGenerator:
    def __init__(self, init_imports: bool = True):
        self.indent_manager = IndentManager()
        self.temp_lines_classification = partial(temp_var_change, self, 'lines_classification')

        self.import_lines = []
        self.inserted_lines = []
        self.code_lines = []
        self.lines_classification = 'code'
        if init_imports:
            self.init_imports()

    def init_imports(self):
        with self.temp_lines_classification('import'):
            self.add('import sys')
            self.add_newlines(num=1)
            self.add('from typing import Any, Dict, List, Union')
            self.add_newlines(num=1)
            self.add('if sys.version_info < (3,8):')
            with self.indent_manager:
                self.add('from typing_extensions import Literal, TypedDict')
            self.add('else:')
            with self.indent_manager:
                self.add('from typing import Literal, TypedDict')
            self.add_newlines(num=2)

    def add_newlines(self, num: int = 1):
        self.add('\n' * num)

    def add_newlines_before_code(self, num: int = 1):
        with self.temp_lines_classification('inserted'):
            self.add('\n' * num)

    def add_comment_from_info(self, info: Dict[str, Any]):
        if 'description' in info:
            newline = '\n'
            self.add(f'# {info["description"].replace(newline, " ")}')

    def add(self, code: str = None, lines: List[str] = None):
        if code:
            lines = [line for line in dedent(code).split('\n')]
            # if we are adding a newline '\n'.split('\n') == ['', ''], which will expand to 2 newlines instead of one
            if lines[-1] == '':
                lines = lines[:-1]
        lines = [f'{self.indent_manager}{li}' for li in lines]
        self.__getattribute__(f'{self.lines_classification}_lines').extend(lines)

    def insert_before_code(self, other: Union['TypingCodeGenerator', 'str']):
        with self.temp_lines_classification('inserted'):
            if isinstance(other, str):
                self.add(other)
            else:
                self.add(lines=other.code_lines)

    def __str__(self):
        return '\n'.join(self.import_lines) + '\n'.join(self.inserted_lines) + '\n'.join(self.code_lines)


class TypedDictGenerator(TypingCodeGenerator):
    def __init__(self, name: str, total: bool):
        super().__init__(init_imports=False)
        self.name = name
        self.total = total
        total_spec = ', total=False' if total else ''
        self.add(f'class {name}(TypedDict{total_spec}):')

    def filter_lines(self, sub_pattern_replacements):
        for index, line in enumerate(self.code_lines):
            if index == 0:
                # skip the class declaration line
                continue
            for sub_p, sub_r in sub_pattern_replacements:
                line = re.sub(sub_p, sub_r, line)
            self.code_lines[index] = line


class IndentManager:
    def __init__(self):
        self._indent = ''

    def __enter__(self):
        self._indent += '    '

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._indent = self._indent[:-4]

    def __str__(self):
        return self._indent


@contextmanager
def temp_var_change(cls_instance: object, var: str, value: Any):
    initial = cls_instance.__getattribute__(var)
    yield cls_instance.__setattr__(var, value)
    cls_instance.__setattr__(var, initial)


if __name__ == '__main__':
    generator = ProtocolTypesGenerator()
    generator.retrieve_top_level_domain()
    generator.gen_spec()
    generator.write_generated_code()
