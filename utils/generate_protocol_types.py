"""
CLI script to generate Protocol types
"""
import asyncio
import json
import logging
import re
import time
from argparse import ArgumentParser
from datetime import datetime
from functools import partial
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Hashable, List, Literal, Match, Tuple, Union

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
    """
    Class for generating a black formatter-semi-compliant code relating relating to the CDP specification.
    Attributes:
        td_references: set of relations of one TypedDict to another. Needed to detect/resolve recursive references
        domains: List containing all the domains of the CDP protocol
        all_known_types: Dict containing all known types. Needed to resolve forward references.
        typed_dicts: Dict of typed_dict_name to TypedDictGenerator(). We need a dict so we can access arbitrary elements
            and update them if a recursive reference is found
        code_gen = instance of TypingCodeGenerator for recording code lines
        _extern_code_gen = instance of TypingCodeGenerator for actually recording code the will appear outside the if
            TYPE_CHECKING guard
    """

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
        self.all_known_types = {}
        self.typed_dicts = {}
        self.code_gen = TypingCodeGenerator()
        self._extern_code_gen = TypingCodeGenerator()

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
        Args:
            line: line in which protocol forward reference occurs.
            fw_ref: whether or not to forward reference the resolved reference
        Returns:
            str: line with resolved forward reference
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
        self.domains = json.loads(page_content)['domains']

    def retrieve_top_level_domain(self):
        """
        Fetches and data, parses it, and sets the class variable 'domains' to it for later use.
        Returns: None
        """
        asyncio.get_event_loop().run_until_complete(self._retrieve_top_level_domain())

    def gen_spec(self):
        """
        Generate the Protocol class file lines within self.code_gen attribute. Uses an IndentManager context manager to
        keep track of the current indentation level. Resolves all forward references. Expands recursive types to an
        approximation of the cyclic type referenced. Wraps protocol class in a if TYPE_CHECKING guard and provides a
        dummy protocol class for runtime for performance.

        Returns: None
        """

        self.generate_header_doc_string()

        logger.info(f'Generating protocol spec')
        t_start = time.perf_counter()

        self.code_gen.add_code('class Protocol:')
        with self.code_gen.indent_manager:
            for domain in self.domains:
                domain_name = domain['domain']
                self.code_gen.add_code(f'class {domain_name}:')
                self.all_known_types[domain_name] = {}
                with self.code_gen.indent_manager:
                    self.code_gen.add_comment_from_info(domain)
                    for type_info in domain.get('types', []):
                        self.add_type_item(type_info, 'id', 'properties', domain_name)

                    for payload in domain.get('events', []):
                        payload["name"] = payload["name"] + 'Payload'
                        self.add_type_item(payload, 'name', 'parameters', domain_name, type_conversion_fallback='None')

                    for command_info in domain.get('commands', []):
                        for td_key, suffix in (('properties', 'Parameters'), ('returns', 'ReturnValues')):
                            command_info['name'] = re.subn(r'(Parameters$|$)', suffix, command_info['name'], 1)[0]
                            self.add_type_item(
                                command_info, 'name', td_key, domain_name, type_conversion_fallback='None'
                            )
                self.code_gen.add_newlines(num=2)

            self.generate_overview()
            self.resolve_all_fw_refs()

        self.expand_recursive_references()
        self.typed_dicts = {k: v for k, v in sorted(self.typed_dicts.items(), key=lambda x: x[0])}
        # all typed dicts are inserted prior to the main Protocol class
        for index, td in enumerate(self.typed_dicts.values()):
            td.add_newlines(num=1)
            self.code_gen.add_code(lines=td.code_lines, lines_classification='inserted')

        self.code_gen.add_code(lines=self._extern_code_gen.code_lines)
        logger.info(f'Generated protocol spec in {time.perf_counter() - t_start:.2f}s')

    def generate_header_doc_string(self):
        """
        Generates a headers doc string for the top of the file.
        Returns: None
        """
        self.code_gen.add_code('"""', lines_classification='inserted')
        self.code_gen.add_code(
            f'''\
            Automatically generated by ./{Path(__file__).relative_to(Path(__file__).parents[1]).as_posix()}
            Attention! This file should *not* be modified directly! Instead, use the script to update it.

            Last regeneration: {datetime.utcnow()}''',
            lines_classification='inserted',
        )
        self.code_gen.add_code('"""', lines_classification='inserted')

    def resolve_all_fw_refs(self) -> None:
        """
        Resolves all forward reference to the root of said references eg 'Protocol.Animation.thingParams' -> thingParams
        Returns: None
        """
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

    def generate_overview(self) -> None:
        """
        Generate several convenience overview classes, listed in overview_info
        Returns: None
        """
        overview_info = {
            'Events': ('events', '\'{domain}.{item_name}\'', True, False),
            'CommandParameters': ('commands', '\'Protocol.{domain}.{item_name}\'', False, False),
            'CommandReturnValues': ('commands', '\'Protocol.{domain}.{item_name}\'', False, False),
            'CommandNames': ('commands', '\'{domain}.{item_name}\'', True, True),
        }

        last_overview_class_name = [*overview_info.keys()][-1]
        for overview_class_name, (domain_key, item_fmt, gen_externally, no_suffix) in overview_info.items():
            overview_code_gen = TypingCodeGenerator(init_imports=False)
            overview_code_gen.add_code(f'class {overview_class_name}:')
            with overview_code_gen.indent_manager:
                for domain in self.domains:
                    if domain_key in domain:
                        overview_code_gen.add_code(f'class {domain["domain"]}:')
                        with overview_code_gen.indent_manager:
                            for item in domain[domain_key]:
                                if no_suffix:
                                    item['name'] = re.sub('(ReturnValues|Parameters)$', '', item['name'])
                                formatted_name = item_fmt.format(domain=domain['domain'], item_name=item['name'])
                                overview_code_gen.add_code(f'{item["name"]} = {formatted_name}')
                        overview_code_gen.add_newlines(num=1)
            if overview_class_name != last_overview_class_name:
                # don't add newlines to EOF
                overview_code_gen.add_newlines(num=1)
            if gen_externally:
                self._extern_code_gen.add_code(lines=overview_code_gen.code_lines)
            else:
                self.code_gen.add_code(lines=overview_code_gen.code_lines)

    def add_type_item(
        self,
        type_info,
        type_name_key,
        td_key,
        domain_name,
        type_conversion_fallback: Union[str, Literal[False]] = False,
    ) -> None:
        """
        Adds a class attr based on type_info, type_name_key, td_key, domain_name, and type_conversion_fallback

        Args:
            type_info: Dict containing info pertaining to the type
            type_name_key: Key to the name of the type
            td_key: Key to the item which contains TypedDict info
            domain_name: Name of domain
            type_conversion_fallback: If not false, used when the type cannot be determined from type_info

        Returns: None
        """
        self.code_gen.add_comment_from_info(type_info)
        item_name = type_info[type_name_key]
        if td_key in type_info:
            td = self.generate_typed_dict(type_info, domain_name)
            self.typed_dicts.update(td)
            type_ = [*td.keys()][0]
            typed_dict = True
        else:
            try:
                type_ = self.convert_js_to_py_type(type_info, domain_name)
            except KeyError:
                if type_conversion_fallback is not False:
                    type_ = type_conversion_fallback
                else:
                    raise
            typed_dict = False

        self.all_known_types[domain_name][item_name] = type_
        if typed_dict:
            # https://github.com/python/mypy/issues/7866
            type_ = f'Union[{type_}]'
        self.code_gen.add_code(f'{item_name} = {type_}')

    def expand_recursive_references(self) -> None:
        """
        Expands recursive references to TypedDicts with Dict[str, Union[Dict[str, Any], str, bool, int, float, List]],
        and adds a comment with the actual type reference.
        Returns: None
        """
        expansion = 'Dict[str, Union[Dict[str, Any], str, bool, int, float, List]]'
        # todo: networkx will soon support sets: https://github.com/networkx/networkx/pull/3907
        for recursive_refs in nx.simple_cycles(nx.DiGraph([*self.td_references])):
            any_recursive_ref = "|".join(recursive_refs)
            for recursing_itm in recursive_refs:
                self.typed_dicts[recursing_itm].filter_lines(
                    (rf'(\s+)(\w+): [\w\[]*?\'({any_recursive_ref})\'\]?', rf'\1# actual: \3\n\1\2: {expansion}'),
                )

    def write_generated_code(self, path: Path) -> None:
        """
        Write generated code lines to the specified path. Writes to a temporary file and checks that file with mypy to
        'resolve' any cyclic references.

        Args:
            path: path to write type code to.

        Returns: None
        """
        if path.is_dir():
            path /= '_protocol.py'
        logger.info(f'Writing generated protocol code to {path}')
        # PyCharm can't handle this path type properly
        # noinspection PyTypeChecker
        with open(path, 'w') as p:
            p.write(str(self.code_gen))

    def generate_typed_dict(self, type_info: Dict[str, Any], domain_name: str) -> Dict[str, 'TypedDictGenerator']:
        """
        Generates TypedDicts based on type_info.

        Args:
            type_info: Dict containing the info for the TypedDict
            domain_name: path to resolve relative forward references in type_info against

        Returns: TypedDict corresponding to type information found in type_info
        """
        items = self._multi_fallback_get(type_info, 'returns', 'parameters', 'properties')
        td_name = self._multi_fallback_get(type_info, 'id', 'name')
        is_total = any(1 for x in items if x.get('optional'))
        td = TypedDictGenerator(td_name, is_total)
        doc_string = TypingCodeGenerator(init_imports=False)
        with td.indent_manager, doc_string.indent_manager:
            needs_closing_triple_q = False
            if 'description' in type_info or any('description' in item for item in items):
                doc_string.add_code('"""')
                needs_closing_triple_q = True
                if 'description' in type_info:
                    doc_string.add_code(type_info['description'])
                    doc_string.add_newlines(num=1)
                if any('description' in item for item in items):
                    doc_string.add_code('Attributes:')

            for item in items:
                type_ = self.convert_js_to_py_type(item, domain_name)
                if 'description' in item:
                    lines = item['description'].split('\n')
                    with doc_string.indent_manager:
                        doc_string.add_code(f'{item["name"]}: {lines[0]}')
                        if len(lines) > 1:
                            with doc_string.indent_manager:
                                doc_string.add_code(lines=lines[1:])
                td.add_code(f'{item["name"]}: {type_}')
            if needs_closing_triple_q:
                doc_string.add_code('"""')
        td.insert_code(lines=doc_string.code_lines)

        return {td_name: td}

    @staticmethod
    def _multi_fallback_get(d: Dict[Hashable, Any], *k: Hashable) -> Any:
        """
        Convenience method to retrieve item from dict with multiple keys as fallbacks for failed accesses

        Args:
            d: Dict to retrieve values from
            k: keys of Dict to retrieve values from
        Returns: Any
            first found value where key in k
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

        Args:
            item_info: Dict or str containing type_info
            domain_name: path to resolve relative forward references in type_info against
        Returns: str
            valid python type, either in the form of an absolute forward reference (eg Protocol.bar.foo) or
            primitive type (eg int, float, str, etc)
        """
        if isinstance(item_info, str):
            type_ = self.js_to_py_types[item_info]
        elif 'items' in item_info:
            assert item_info['type'] == 'array'
            if '$ref' in item_info['items']:
                ref = item_info['items']['$ref']
                type_ = f'List[{self.get_forward_ref(ref, domain_name)}]'
            else:
                type_ = f'List[{self.convert_js_to_py_type(item_info["items"]["type"], domain_name)}]'
        else:
            if '$ref' in item_info:
                type_ = self.get_forward_ref(item_info['$ref'], domain_name)
            else:
                if 'enum' in item_info:
                    _enum_vals = ', '.join([f'\'{x}\'' for x in item_info['enum']])
                    type_ = f'Literal[{_enum_vals}]'
                else:
                    type_ = self.js_to_py_types[item_info['type']]

        return type_

    @staticmethod
    def get_forward_ref(relative_ref: str, potential_domain_context: str) -> str:
        """
        Generates a forward absolute forward reference to Protocol class attr. If the reference is relative
        to a nested class, the full path is resolved against potential_domain_context. In the case of
        the reference being relative to the Protocol class, the path is simple resolved against the Protocol class

        Args:
            relative_ref: reference to another class, in the form of foo or foo.bar
            potential_domain_context: context to resolve class against if relative_ref is relative to it

        Returns: str
            absolute forward reference to nested class attr
        """
        if len(relative_ref.split('.')) == 2:
            non_fw_ref = f'Protocol.{relative_ref}'
        else:
            non_fw_ref = f'Protocol.{potential_domain_context}.{relative_ref}'
        return f'\'{non_fw_ref}\''


class TypingCodeGenerator:
    """
    Class to facilitate the generation of typing related related code

    Attributes:
        indent_manager: instance of IndentManager. Used to manage the current indentation level
        import_lines: List containing lines of import code
        inserted_lines: List containing lines of code before the main body
        code_lines: List containing lines of code
        lines_classification: Classification of the lines, the value should be one such that self.<value>_lines is
            defined. The default is 'code'
    """

    def __init__(self, init_imports: bool = True):
        """
        Args:
            init_imports: Whether or not to write importing code to self.import_lines, defaults to True
        """
        self.indent_manager = IndentManager()
        self.import_lines = []
        self.inserted_lines = []
        self.code_lines = []
        self.lines_classification = 'code'
        if init_imports:
            self.init_imports()

    def init_imports(self) -> None:
        """
        Writes import code relating to typing to self.import_lines
        Returns: None
        """
        self.lines_classification = 'import'
        self.add_code('import sys')
        self.add_newlines(num=1)
        self.add_code('from typing import Any, Dict, List, TYPE_CHECKING, Union')
        self.add_newlines(num=1)
        self.add_code('if sys.version_info < (3, 8):')
        with self.indent_manager:
            self.add_code('from typing_extensions import Literal, TypedDict')
        self.add_code('else:')
        with self.indent_manager:
            self.add_code('from typing import Literal, TypedDict')
        self.add_newlines(num=1)
        self.lines_classification = 'code'

    def add_newlines(self, num: int = 1, lines_classification: str = None) -> None:
        """
        Adds num newlines
        Args:
            num: number of newlines to add
            lines_classification: str of lines_classification, defaults to self.lines_classification

        Returns: None
        """
        self.add_code('\n' * num, lines_classification)

    def add_comment_from_info(self, info: Dict[str, Any]) -> None:
        """
        Adds a comment to code_lines if a description is defined in info
        Args:
            info: Dict possible containing the key info

        Returns: None
        """
        if 'description' in info:
            newline = '\n'
            self.add_code(f'# {info["description"].replace(newline, " ")}')

    def add_code(self, code: str = None, lines: List[str] = None, lines_classification: str = None) -> None:
        """
        Adds code from a string or code from lines. If code is not None, lines is assigned to the str dedented and
        split by newlines. Each line in lines is applied the current indent level before being added to the
        <lines_classification>_lines list
        Args:
            code: str containing code
            lines: List[str] containing code
            lines_classification: str of lines_classification, defaults to self.lines_classification

        Returns: None
        """
        assert code is not None or lines is not None, 'One of code or lines must be specified'
        lines_classification = lines_classification or self.lines_classification
        if code is not None:
            if all([char == '\n' for char in code]):
                # if we are adding a newline, '\n'.split('\n') == ['', ''], which will expand to 2 newlines instead of
                lines = ['' for _ in range(code.count('\n'))]
            else:
                lines = dedent(code).split('\n')
        # don't indent empty lines
        lines = [f'{self.indent_manager if li else ""}{li}' for li in lines]
        self.__getattribute__(f'{lines_classification}_lines').extend(lines)

    def __str__(self):
        return '\n'.join([*self.import_lines, *self.inserted_lines, *self.code_lines])


class TypedDictGenerator(TypingCodeGenerator):
    """
    Class to manage creation of TypedDicts specifically. Does not initialize imports.
    """

    def __init__(self, name: str, total: bool):
        super().__init__(init_imports=False)
        self.name = name
        self.total = total
        total_spec = ', total=False' if total else ''
        self.add_code(f'class {name}(TypedDict{total_spec}):')

    def filter_lines(self, *sub_pattern_replacements: Tuple[str, Any]) -> None:
        """
        Performs re.sub on all code_lines (except for the first one) according to sub_pattern_replacements. Each
        sub_sub_pattern_replacements should be a re pattern and regex replacement function/regex replacement string
        Args:
            sub_pattern_replacements: tuple containing a regex pattern and
                regex replacement function or regex replacement string

        Returns: None
        """
        # temp_code_lines = self.code_lines[:]
        # self.code_lines = [self.code_lines[0]]
        filtered_lines = []
        for index, line in enumerate(self.code_lines[1:]):
            for sub_p, sub_r in sub_pattern_replacements:
                line = re.sub(sub_p, sub_r, line)
            filtered_lines.extend(line.split('\n'))
        self.code_lines = self.code_lines[:1] + filtered_lines

    def insert_code(self, code: str = None, lines: List[str] = None, lines_classification: str = None) -> None:
        old_lines = self.code_lines[1:]
        self.code_lines = self.code_lines[:1]
        self.add_code(code, lines, lines_classification)
        self.add_code(lines=old_lines)


class IndentManager:
    """
    Simple class which can be used with a with statement to increment/decrement the current indent level/
    """

    def __init__(self):
        self.indent = ''

    def __enter__(self) -> 'IndentManager':
        self.indent += '    '
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.indent = self.indent[:-4]

    def __str__(self) -> str:
        return self.indent


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '--output',
        '-o',
        help='dir or file to output to',
        default=Path(__file__).parents[1] / 'pyppeteer' / 'models' / '_protocol.py',
    )
    generator = ProtocolTypesGenerator()
    generator.retrieve_top_level_domain()
    generator.gen_spec()
    generator.write_generated_code(path=parser.parse_args().output)
