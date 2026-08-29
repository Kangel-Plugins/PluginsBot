import ast
import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from PluginsBot.config import KNOWN_LIBS
from PluginsBot.utils.store_utils import _extract_string_value, normalize_min_version, normalize_requirements


def extract_plugin_metadata(plugin_content: str) -> Dict[str, Any]:
    metadata = {}

    patterns = {
        "id": r'__id__\s*=\s*["\']([^"\']+)["\']',
        "name": r'__name__\s*=\s*["\']([^"\']+)["\']',
        "version": r'__version__\s*=\s*["\']([^"\']+)["\']',
        "min_version": r'__min_version__\s*=\s*["\']([^"\']+)["\']',
        "icon": r'__icon__\s*=\s*["\']([^"\']+)["\']',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, plugin_content)
        if match:
            metadata[key] = match.group(1)

    app_version = (
        _extract_string_value(plugin_content, "__app_version__")
        or _extract_string_value(plugin_content, "__app_cersion__")
    )
    if app_version:
        metadata["app_version"] = app_version
        metadata.setdefault("min_version", normalize_min_version(app_version))

    author = _extract_string_value(plugin_content, "__author__")
    if author:
        metadata['author'] = author

    description = _extract_string_value(plugin_content, "__description__")
    if description:
        metadata['description'] = description
    requirements = normalize_requirements(_extract_string_value(plugin_content, "__requirements__"))
    if requirements:
        metadata['requirements'] = requirements
    print(f"\nИзвлеченные метаданные:")
    print(f"  ID: {metadata.get('id', 'N/A')}")
    print(f"  Name: {metadata.get('name', 'N/A')}")
    print(f"  Version: {metadata.get('version', 'N/A')}")
    print(f"  Author: {metadata.get('author', 'N/A')}")
    print(f"  App Version: {metadata.get('app_version', 'N/A')}")
    if description:
        desc_preview = description[:100] + "..." if len(description) > 100 else description
        print(f"  Description ({len(description)} chars): {desc_preview}")
    else:
        print(f"  Description: N/A")
    print(f"  Icon: {metadata.get('icon', 'N/A')}")
    print(f"  Requirements: {', '.join(requirements) if requirements else 'N/A'}")

    return metadata


def detect_dependencies(plugin_content: str) -> List[str]:

    dependencies = []

    import_patterns = [
        r'from\s+(\w+)\s+import',
        r'import\s+(\w+)',
    ]

    for pattern in import_patterns:
        matches = re.findall(pattern, plugin_content)
        for match in matches:
            if match in KNOWN_LIBS:
                if match not in dependencies:
                    dependencies.append(match)

    return dependencies


ELYX_META_FILES = ('metainfo.json', 'metainfo.yml', 'metainfo.yaml', 'meta.json', 'meta.yml')
ELYX_REFMAP_FILES = ('refmap.yaml', 'refmap.yml', 'refmap.json')
ELYX_META_FIELDS = {
    'id': 'id',
    'name': 'name',
    'version': 'version',
    'author': 'author',
    'description': 'description',
    'icon': 'icon',
    'min_version': 'min_version',
    'app_version': 'app_version',
    'sdk_version': 'sdk_version',
    'elyx_version': 'elyx_version',
}


def extract_elyx_metadata(zip_content: bytes) -> Dict[str, Any]:
    metadata = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
            metadata = _extract_elyx_metadata_from_zip(zf)
    except Exception as e:
        print(f"[Elyx] Ошибка извлечения метаданных: {e}")
    return metadata


def extract_elyx_metadata_from_file(plugin_path: str) -> Dict[str, Any]:
    metadata = {}
    try:
        with zipfile.ZipFile(plugin_path, 'r') as zf:
            metadata = _extract_elyx_metadata_from_zip(zf)
    except Exception as e:
        print(f"[Elyx] Ошибка извлечения метаданных из файла: {e}")
    return metadata


def _extract_elyx_metadata_from_zip(zf) -> Dict[str, Any]:
    metadata = {}
    names = zf.namelist()
    print(f"[Elyx] Files in archive: {names}")

    refmap_path = None
    for candidate in ELYX_REFMAP_FILES:
        if candidate in names:
            refmap_path = candidate
            break

    refmap = {}
    if refmap_path:
        print(f"[Elyx] Найден refmap: {refmap_path}")
        try:
            refmap = _read_structured_file(zf, refmap_path)
            if isinstance(refmap, dict):
                print(f"[Elyx] refmap содержимое: {refmap}")
            else:
                refmap = {}
        except Exception as e:
            print(f"[Elyx] Ошибка чтения refmap: {e}")
            refmap = {}

    metainfo_path = None
    metainfo_format = None
    explicit = refmap.get('metainfo')
    if explicit:
        resolved = _resolve_archive_path(names, explicit)
        if resolved:
            metainfo_path, metainfo_format = resolved
            print(f"[Elyx] metainfo из refmap: {metainfo_path}")
        else:
            print(f"[Elyx] metainfo из refmap не найден в архиве: {explicit}")

    if not metainfo_path:
        for candidate in ELYX_META_FILES:
            if candidate in names:
                metainfo_path = candidate
                metainfo_format = 'json' if candidate.endswith('.json') else 'yaml'
                print(f"[Elyx] Найден {candidate} в корне")
                break

    if not metainfo_path:
        print(f"[Elyx] metainfo не в корне, ищу в подпапках...")
        for name in names:
            base = name.rsplit('/', 1)[-1]
            if base in ELYX_META_FILES:
                metainfo_path = name
                metainfo_format = 'json' if base.endswith('.json') else 'yaml'
                print(f"[Elyx] Метаданные найдены в подпапке: {metainfo_path}")
                break

    if not metainfo_path:
        print(f"[Elyx] metainfo не найден в архиве!")
        return metadata

    try:
        if metainfo_format == 'py':
            meta = _extract_python_metadata(zf.read(metainfo_path).decode('utf-8'))
        else:
            meta = _read_structured_file(zf, metainfo_path)
        if not isinstance(meta, dict):
            print(f"[Elyx] Метаданные не являются словарем: {type(meta)}")
            return metadata
    except Exception as e:
        print(f"[Elyx] Ошибка парсинга метаданных: {e}")
        return metadata

    print(f"[Elyx] Распарсенные метаданные: {meta}")

    normalized_meta = {}
    for key, value in meta.items():
        clean_key = key.strip('_') if key.startswith('__') and key.endswith('__') else key
        normalized_meta[clean_key] = value

    for meta_key, json_key in ELYX_META_FIELDS.items():
        if meta_key in normalized_meta:
            metadata[json_key] = normalized_meta[meta_key]

    app_version = metadata.get('app_version')
    if app_version and not metadata.get('min_version'):
        metadata['min_version'] = normalize_min_version(app_version)

    description = metadata.get('description')
    if isinstance(description, str) and '{' in description:
        print(f"[Elyx] Description содержит плейсхолдер, ищу в локалях...")
        resolved, descriptions = _resolve_description_placeholders(
            description, zf, refmap.get('strings')
        )
        if descriptions:
            metadata['descriptions'] = descriptions
        metadata['description'] = resolved

    requirements = normalize_requirements(normalized_meta.get('requirements'))
    if requirements:
        metadata['requirements'] = requirements

    requires = _normalize_requires(normalized_meta.get('requires'))
    if requires:
        metadata['requires'] = requires

    return metadata


def _resolve_archive_path(names: List[str], path: Any) -> Optional[Tuple[str, str]]:
    p = str(path).lstrip('./')
    if p in names:
        return p, _metainfo_format(p)
    for name in names:
        if name == p or name.endswith('/' + p):
            return name, _metainfo_format(name)
    return None


def _metainfo_format(path: str) -> str:
    if path.endswith('.json'):
        return 'json'
    if path.endswith('.py'):
        return 'py'
    return 'yaml'


def _read_structured_file(zf, path: str) -> Any:
    raw = zf.read(path).decode('utf-8')
    if path.endswith('.json'):
        return json.loads(raw)
    return _parse_simple_yaml(raw)


def _extract_python_metadata(content: str) -> Dict[str, Any]:
    meta = {}
    for key in ['id', 'name', 'version', 'author', 'description', 'icon',
                'min_version', 'app_version', 'sdk_version']:
        for variant in (f'__{key}__', key):
            value = _extract_string_value(content, variant)
            if value is not None:
                meta[key] = value
                break
    requirements = _extract_python_requirements(content)
    if requirements is not None:
        meta['requirements'] = requirements
    return meta


def _extract_python_requirements(content: str) -> Optional[str]:
    match = re.search(r'^\s*(?:__)?requirements(?:__)?\s*=\s*', content, re.MULTILINE)
    if not match:
        return None
    start = match.end()
    depth = 0
    quote = None
    i = start
    end = len(content)
    while i < end:
        ch = content[i]
        if quote:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch in ('(', '[', '{'):
            depth += 1
        elif ch in (')', ']', '}'):
            depth -= 1
            if depth <= 0:
                i += 1
                break
        elif depth == 0 and ch == '\n':
            break
        i += 1
    literal_str = content[start:i].strip()
    try:
        parsed = ast.literal_eval(literal_str)
    except Exception:
        parsed = literal_str
    if isinstance(parsed, (list, tuple)):
        return ','.join(str(x) for x in parsed)
    if isinstance(parsed, str):
        return parsed
    return None


def _normalize_requires(requires_value: Any) -> List[Dict[str, Any]]:
    if not requires_value:
        return []

    if isinstance(requires_value, str):
        items = [(part.strip(), None) for part in requires_value.split(',') if part.strip()]
    elif isinstance(requires_value, dict):
        items = list(requires_value.items())
    elif isinstance(requires_value, list):
        items = []
        for entry in requires_value:
            if isinstance(entry, dict):
                items.extend(entry.items())
            elif isinstance(entry, str) and entry.strip():
                items.append((entry.strip(), None))
    else:
        return []

    result = []
    for key, url in items:
        key = str(key).strip()
        if not key:
            continue
        entry: Dict[str, Any] = {'id': None, 'min_version': None, 'url': None}
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', key)
        if match:
            entry['id'] = match.group(1).strip()
            entry['min_version'] = match.group(2).strip()
        else:
            entry['id'] = key
        if url is not None:
            url_str = str(url).strip()
            entry['url'] = url_str or None
        result.append(entry)
    return result


def _resolve_description_placeholders(description: str, zf, strings_ref: Any = None) -> Tuple[str, Dict[str, str]]:
    placeholders = re.findall(r'\{([a-zA-Z0-9_]+)\}', description)
    if not placeholders:
        return description, {}

    locales = _load_locales(zf, strings_ref)
    langs = [lang for lang in ('ru', 'en') if lang in locales]
    langs += [lang for lang in locales if lang not in langs]

    resolved_by_lang = {}
    for lang in langs:
        data = locales[lang]
        resolved = description
        for key in placeholders:
            value = data.get(key)
            if not value:
                value = key
            resolved = resolved.replace('{' + key + '}', str(value))
        resolved_by_lang[lang] = resolved
        preview = resolved.replace('\n', ' ')[:60]
        print(f"[Elyx] Description ({lang}): {preview}...")

    default = (
        resolved_by_lang.get('ru')
        or resolved_by_lang.get('en')
        or next(iter(resolved_by_lang.values()), description)
    )
    return default, resolved_by_lang


def _load_locales(zf, strings_ref: Any = None) -> Dict[str, Dict[str, Any]]:
    names = zf.namelist()
    locale_files = []

    if strings_ref:
        ref = str(strings_ref).strip('/')
        if ref.endswith(('.json', '.yml', '.yaml')):
            if ref in names:
                locale_files = [ref]
            else:
                for n in names:
                    if n == ref or n.endswith('/' + ref):
                        locale_files = [n]
                        break
        else:
            prefix = ref + '/'
            locale_files = [n for n in names
                           if n.startswith(prefix) and n.endswith(('.json', '.yml', '.yaml'))]

    if not locale_files:
        for n in names:
            if any(n.endswith(ext) for ext in ['.json', '.yml', '.yaml']):
                if ('locales/' in n or 'strings/' in n) or (n.startswith('strings_') and '/' not in n):
                    locale_files.append(n)

    locales = {}
    for name in sorted(locale_files):
        try:
            data = _read_structured_file(zf, name)
            if not isinstance(data, dict):
                continue
            lang = _locale_lang(name)
            locales.setdefault(lang, {})
            locales[lang].update(data)
            print(f"[Elyx] Локали {name}: {len(data)} ключей")
        except Exception:
            pass
    return locales


def _locale_lang(name: str) -> str:
    base = name.rsplit('/', 1)[-1]
    for prefix in ('strings_', 'string_', 'locale_', 'lang_'):
        if base.startswith(prefix):
            base = base[len(prefix):]
            break
    base = base.rsplit('.', 1)[0]
    base = base.lower().split('_')[0].split('-')[0]
    return base or 'en'


def _is_open_scalar(value: str) -> bool:
    value = value.strip()
    if len(value) >= 2 and value[0] in ('"', "'"):
        return not value.endswith(value[0])
    if not value or value[0] in ('[', '{', '-'):
        return False
    low = value.lower()
    if low in ('true', 'false', 'null', '~'):
        return False
    if re.fullmatch(r'-?\d+(\.\d+)?', value):
        return False
    return True


def _fold_multiline_scalars(lines):
    if not lines:
        return lines
    folded = []
    n = len(lines)
    i = 0
    while i < n:
        indent, line = lines[i]
        if ':' in line:
            key, _, raw_value = line.partition(':')
            value = raw_value.strip()
            if value and _is_open_scalar(value):
                parts = [value]
                j = i + 1
                while j < n and lines[j][0] > indent:
                    parts.append(lines[j][1])
                    j += 1
                if j > i + 1:
                    folded.append((indent, f'{key}: {" ".join(parts)}'))
                    i = j
                    continue
        folded.append((indent, line))
        i += 1
    return folded


def _parse_simple_yaml(content: str) -> Dict[str, Any]:
    lines = []
    for raw in content.split('\n'):
        if '\t' in raw:
            raw = raw.expandtabs(4)
        stripped = raw.strip()
        if not stripped or stripped.startswith('#') or stripped in ('---', '...'):
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        lines.append((indent, stripped))

    lines = _fold_multiline_scalars(lines)

    def _parse_block(start: int, indent: int):
        if start >= len(lines):
            return {}, start
        cur_indent, line = lines[start]
        if cur_indent < indent:
            return {}, start

        if line.startswith('- '):
            items = []
            idx = start
            while idx < len(lines):
                i, l = lines[idx]
                if i != indent or not l.startswith('- '):
                    break
                item_text = l[2:].strip()
                if not item_text:
                    if idx + 1 < len(lines) and lines[idx + 1][0] > indent:
                        child, idx = _parse_block(idx + 1, lines[idx + 1][0])
                        items.append(child)
                    else:
                        items.append(None)
                        idx += 1
                elif ':' in item_text and not item_text.startswith(('"', "'")):
                    key, _, val = item_text.partition(':')
                    items.append({key.strip(): _parse_yaml_scalar(val.strip())})
                    idx += 1
                else:
                    items.append(_parse_yaml_scalar(item_text))
                    idx += 1
            return items, idx

        result = {}
        idx = start
        while idx < len(lines):
            i, l = lines[idx]
            if i != indent:
                break
            if ':' not in l:
                idx += 1
                continue
            key, _, raw_value = l.partition(':')
            key = key.strip()
            if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                key = key[1:-1]
            raw_value = raw_value.strip()
            if not raw_value:
                if idx + 1 < len(lines) and lines[idx + 1][0] > indent:
                    child, idx = _parse_block(idx + 1, lines[idx + 1][0])
                else:
                    child = {}
                    idx += 1
                result[key] = child
            else:
                result[key] = _parse_yaml_scalar(raw_value)
                idx += 1
        return result, idx

    result, _ = _parse_block(0, 0)
    return result


def _parse_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ''
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith('{') and value.endswith('}'):
        inner = value[1:-1]
        obj = {}
        if inner.strip():
            for part in inner.split(','):
                k, _, v = part.partition(':')
                obj[k.strip()] = _parse_yaml_scalar(v.strip())
        return obj
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1]
        if not inner.strip():
            return []
        return [_parse_yaml_scalar(item.strip()) for item in inner.split(',')]
    hash_pos = value.find(' #')
    if hash_pos != -1:
        value = value[:hash_pos].rstrip()
    low = value.lower()
    if low in ('null', '~'):
        return None
    if low == 'true':
        return True
    if low == 'false':
        return False
    if re.fullmatch(r'-?\d+', value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r'-?\d+\.\d+', value):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def is_elyx_plugin(filename: str) -> bool:
    return filename.lower().endswith('.zip') or filename.lower().endswith('.elyx') or filename.lower().endswith('.eaf')
