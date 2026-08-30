
import json
import os
import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from PluginsBot.config import STORE_JSON_FILE, PLUGINS_DIR, KNOWN_LIBS


def _extract_string_value(content: str, field_name: str) -> Optional[str]:
    triple_patterns = [
        (re.compile(rf'^\s*{re.escape(field_name)}\s*=\s*"""(.*?)"""', re.MULTILINE | re.DOTALL), '"""'),
        (re.compile(rf"^\s*{re.escape(field_name)}\s*=\s*'''(.*?)'''", re.MULTILINE | re.DOTALL), "'''"),
    ]

    for pattern, _ in triple_patterns:
        match = pattern.search(content)
        if match:
            return match.group(1)

    start_pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*=\s*(?P<value>.+)$",
        re.MULTILINE,
    )
    match = start_pattern.search(content)
    if not match:
        return None

    start_pos = match.start("value")
    raw_value = match.group("value").strip()

    if raw_value.startswith("("):
        depth = 1
        pos = start_pos + 1
        while pos < len(content) and depth > 0:
            char = content[pos]
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            pos += 1

        tuple_content = content[start_pos:pos]

        inner = tuple_content[1:-1] if tuple_content.endswith(')') else tuple_content[1:]

        strings = re.findall(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', inner, re.DOTALL)
        result = []
        for s in strings:
            str_content = s[0] if s[0] is not None else s[1] if s[1] is not None else ""
            str_content = str_content.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
            result.append(str_content)

        return ''.join(result) if result else None

    return _strip_literal(raw_value)


def _strip_literal(raw_value: str) -> Optional[str]:
    if not raw_value:
        return None

    if raw_value[0] in {'"', "'"}:
        quote = raw_value[0]
        i = 1
        result = []
        while i < len(raw_value):
            char = raw_value[i]
            if char == '\\' and i + 1 < len(raw_value):
                next_char = raw_value[i + 1]
                if next_char == 'n':
                    result.append('\n')
                elif next_char == 't':
                    result.append('\t')
                elif next_char == 'r':
                    result.append('\r')
                elif next_char in ['"', "'", '\\']:
                    result.append(next_char)
                else:
                    result.append('\\' + next_char)
                i += 2
            elif char == quote:
                return ''.join(result)
            else:
                result.append(char)
                i += 1
        return ''.join(result) if result else None

    if raw_value.startswith("("):
        try:
            import ast
            return ast.literal_eval(raw_value)
        except (ValueError, SyntaxError):
            return raw_value

    import json
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value.strip()


def normalize_min_version(version_expr: Optional[str]) -> Optional[str]:
    if not version_expr:
        return None

    version_expr = str(version_expr).strip()
    match = re.search(r'(\d+(?:\.\d+)+)', version_expr)
    if match:
        return match.group(1)

    return version_expr or None


def normalize_requirements(requirements_value: Any) -> List[str]:
    if not requirements_value:
        return []

    if isinstance(requirements_value, str):
        raw_items = requirements_value.split(",")
    elif isinstance(requirements_value, (list, tuple, set)):
        raw_items = list(requirements_value)
    else:
        raw_items = [requirements_value]

    normalized = []
    for item in raw_items:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def calculate_plugin_hash(plugin_filename: str) -> Optional[str]:
    plugin_path = os.path.join(PLUGINS_DIR, plugin_filename)

    if not os.path.exists(plugin_path):
        print(f"⚠️ Файл плагина не найден для расчета хеша: {plugin_path}")
        return None

    try:
        sha256_hash = hashlib.sha256()
        with open(plugin_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        hash_value = sha256_hash.hexdigest()
        print(f"✓ Рассчитан хеш для {plugin_filename}: {hash_value}")
        return hash_value
    except Exception as e:
        print(f"❌ Ошибка при расчете хеша для {plugin_filename}: {e}")
        return None


def extract_metadata_from_plugin(plugin_filename: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], List[str], List[Dict], Dict[str, str]]:

    name = None
    version = None
    min_version = None
    app_version = None
    icon = None
    author = None
    description = None
    requirements: List[str] = []
    requires: List[Dict] = []
    descriptions: Dict[str, str] = {}

    plugin_path = os.path.join(PLUGINS_DIR, plugin_filename)

    if not os.path.exists(plugin_path):
        return name, version, min_version, app_version, icon, author, description, requirements, requires, descriptions

    is_elyx = plugin_filename.lower().endswith('.zip') or plugin_filename.lower().endswith('.elyx') or plugin_filename.lower().endswith('.eaf')

    if is_elyx:
        print(f"[DEBUG] Elyx архив detected: {plugin_filename}")
        from PluginsBot.utils.plugin_utils import extract_elyx_metadata_from_file
        elyx_meta = extract_elyx_metadata_from_file(plugin_path)
        name = elyx_meta.get('name')
        version = elyx_meta.get('version')
        min_version = elyx_meta.get('min_version')
        app_version = elyx_meta.get('app_version')
        icon = elyx_meta.get('icon')
        author = elyx_meta.get('author')
        description = elyx_meta.get('description')
        requirements = elyx_meta.get('requirements', [])
        requires = elyx_meta.get('requires', [])
        descriptions = elyx_meta.get('descriptions', {})
        print(f"[DEBUG] Elyx метаданные из {plugin_filename}: {elyx_meta}")
        return name, version, min_version, app_version, icon, author, description, requirements, requires, descriptions

    try:
        with open(plugin_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"[DEBUG] Чтение файла {plugin_filename} ({len(content)} символов)")

        name = _extract_string_value(content, "__name__")
        if name:
            print(f"[DEBUG] ✓ Найден __name__: {repr(name)}")
        else:
            print(f"[DEBUG] ✗ __name__ не найден")

        version = _extract_string_value(content, "__version__")
        if version:
            print(f"[DEBUG] ✓ Найден __version__: {repr(version)}")
        else:
            print(f"[DEBUG] ✗ __version__ не найден")

        min_version = _extract_string_value(content, "__min_version__")
        if min_version:
            print(f"[DEBUG] ✓ Найден __min_version__: {repr(min_version)}")
        else:
            print(f"[DEBUG] ✗ __min_version__ не найден")

        app_version = _extract_string_value(content, "__app_version__")
        if not app_version:
            app_version = _extract_string_value(content, "__app_cersion__")
        if app_version:
            print(f"[DEBUG] ✓ Найден __app_version__/__app_cersion__: {repr(app_version)}")
            if not min_version:
                min_version = normalize_min_version(app_version)
                print(f"[DEBUG] → Использую app_version как min_version: {repr(min_version)}")
        else:
            print(f"[DEBUG] ✗ __app_version__/__app_cersion__ не найден")

        icon = _extract_string_value(content, "__icon__")
        if icon:
            print(f"[DEBUG] ✓ Найден __icon__: {repr(icon)}")
        else:
            print(f"[DEBUG] ✗ __icon__ не найден")

        author = _extract_string_value(content, "__author__")
        if author:
            print(f"[DEBUG] ✓ Найден __author__: {repr(author)}")
        else:
            print(f"[DEBUG] ✗ __author__ не найден")

        description = _extract_string_value(content, "__description__")
        if description:
            desc_preview = description[:100] + "..." if len(description) > 100 else description
            print(f"[DEBUG] ✓ Найден __description__ ({len(description)} chars): {repr(desc_preview)}")
        else:
            print(f"[DEBUG] ✗ __description__ не найден")

        requirements = normalize_requirements(_extract_string_value(content, "__requirements__"))
        if requirements:
            print(f"[DEBUG] ✓ Найден __requirements__: {requirements}")
        else:
            print(f"[DEBUG] ✗ __requirements__ не найден")

    except Exception as e:
        print(f"⚠️ Ошибка при извлечении метаданных из {plugin_filename}: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")

    if not version:
        version = "1.0.0"
        print(f"[DEBUG] → Используется значение по умолчанию: version={version}")
    if not min_version:
        min_version = "11.12.0"
        print(f"[DEBUG] → Используется значение по умолчанию: min_version={min_version}")
    if not description:
        description = ""

    return name, version, min_version, app_version, icon, author, description, requirements, requires, descriptions


def get_plugin_entry(plugin_id: str) -> Optional[Dict]:
    try:
        if not os.path.exists(STORE_JSON_FILE):
            return None
        with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
            store_data = json.load(f)
        entry = store_data.get(plugin_id)
        return entry if isinstance(entry, dict) else None
    except Exception:
        return None


def get_plugin_filename_by_id(plugin_id: str) -> Optional[str]:
    entry = get_plugin_entry(plugin_id)
    if not entry:
        return None

    url = entry.get("url", "")
    if not url:
        return None

    filename = os.path.basename(url)
    return filename or None


def add_plugin_to_store_json(plugin_id: str, url: str, dependencies: List[str] = None, plugin_filename: str = None, status: str = None, signature: str = None) -> bool:

    try:
        if os.path.exists(STORE_JSON_FILE):
            with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
                store_data = json.load(f)
        else:
            store_data = {}

        name = None
        version = None
        min_version = None
        app_version = None
        icon = None
        author = None
        description = None
        requirements = []
        requires = []
        descriptions = {}
        plugin_hash = None

        if plugin_filename:
            print(f"\n[DEBUG] Извлечение метаданных для {plugin_id} из файла: {plugin_filename}")
            name, version, min_version, app_version, icon, author, description, requirements, requires, descriptions = extract_metadata_from_plugin(plugin_filename)
            plugin_hash = calculate_plugin_hash(plugin_filename)

        plugin_entry = {
            "url": url
        }

        if name:
            plugin_entry["name"] = name
        if version:
            plugin_entry["version"] = version
        if min_version:
            plugin_entry["min_version"] = min_version
        if app_version:
            plugin_entry["app_version"] = app_version
        if icon:
            plugin_entry["icon"] = icon
        if author:
            plugin_entry["author"] = author
        if description:
            plugin_entry["description"] = description
        if descriptions:
            for lang, desc in descriptions.items():
                plugin_entry[f"description_{lang}"] = desc
        if requirements:
            plugin_entry["requirements"] = requirements
        if requires:
            plugin_entry["requires"] = requires
        if dependencies:
            plugin_entry["dependencies"] = dependencies
        if plugin_hash:
            plugin_entry["hash"] = plugin_hash
        if signature:
            plugin_entry["signature"] = signature

        if status:
            plugin_entry["status"] = status
        elif plugin_id in store_data:
            plugin_entry["status"] = store_data[plugin_id].get("status", "plugin")
        else:
            plugin_entry["status"] = "library" if plugin_id in KNOWN_LIBS else "plugin"

        is_new = plugin_id not in store_data

        if not is_new and "legacy_version" in store_data[plugin_id]:
            plugin_entry["legacy_version"] = store_data[plugin_id]["legacy_version"]

        store_data[plugin_id] = plugin_entry

        reordered = {plugin_id: plugin_entry}
        for k, v in store_data.items():
            if k != plugin_id:
                reordered[k] = v
        store_data = reordered

        with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(store_data, f, indent=4, ensure_ascii=False)

        action = "добавлен" if is_new else "обновлен"
        print(f"\n✅ Плагин {plugin_id} успешно {action} в store.json")
        return True

    except FileNotFoundError as e:
        print(f"❌ Файл store.json не найден: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return False
    except IOError as e:
        print(f"❌ Ошибка при работе с файлом store.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при добавлении плагина в store.json: {type(e).__name__}: {e}")
        return False


def is_plugin_in_store(plugin_id: str) -> Tuple[bool, Optional[str]]:
    try:
        if not os.path.exists(STORE_JSON_FILE):
            return False, None
        with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
            store_data = json.load(f)
        if plugin_id in store_data:
            return True, store_data[plugin_id].get("status")
        return False, None
    except Exception:
        return False, None


def update_store_json():
    try:
        if not os.path.exists(STORE_JSON_FILE):
            print(f"❌ Файл store.json не найден: {STORE_JSON_FILE}")
            return False

        with open(STORE_JSON_FILE, "r", encoding="utf-8") as f:
            store_data = json.load(f)

        updated_plugins = 0
        skipped_count = 0
        not_found_count = 0
        no_metadata_count = 0
        hashes_updated = 0

        for plugin_id, plugin_entry in store_data.items():
            url = plugin_entry.get("url", "")
            if not url:
                skipped_count += 1
                continue

            plugin_filename = os.path.basename(url)

            name, version, min_version, app_version, icon, author, description, requirements, requires, descriptions = extract_metadata_from_plugin(plugin_filename)

            plugin_path = os.path.join(PLUGINS_DIR, plugin_filename)
            if not os.path.exists(plugin_path):
                not_found_count += 1
                continue

            updated = False
            if name and not plugin_entry.get("name"):
                plugin_entry["name"] = name
                updated = True

            if version and not plugin_entry.get("version"):
                plugin_entry["version"] = version
                updated = True

            if min_version and not plugin_entry.get("min_version"):
                plugin_entry["min_version"] = min_version
                updated = True

            if app_version and not plugin_entry.get("app_version"):
                plugin_entry["app_version"] = app_version
                updated = True

            if icon and not plugin_entry.get("icon"):
                plugin_entry["icon"] = icon
                updated = True

            if author and not plugin_entry.get("author"):
                plugin_entry["author"] = author
                updated = True

            if description and not plugin_entry.get("description"):
                plugin_entry["description"] = description
                updated = True

            if requirements and "requirements" not in plugin_entry:
                plugin_entry["requirements"] = requirements
                updated = True

            if requires and "requires" not in plugin_entry:
                plugin_entry["requires"] = requires
                updated = True

            if descriptions:
                for lang, desc in descriptions.items():
                    field = f"description_{lang}"
                    if field not in plugin_entry:
                        plugin_entry[field] = desc
                        updated = True

            plugin_hash = calculate_plugin_hash(plugin_filename)
            if plugin_hash:
                plugin_entry["hash"] = plugin_hash
                if "hash" not in store_data[plugin_id] or store_data[plugin_id].get("hash") != plugin_hash:
                    updated = True
                    hashes_updated += 1

            if updated:
                updated_plugins += 1
            else:
                skipped_count += 1
            if not any([name, version, min_version, app_version, icon, author, description, requirements, requires]):
                no_metadata_count += 1

        with open(STORE_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(store_data, f, indent=4, ensure_ascii=False)

        print(f"✅ Обновление store.json завершено:")
        print(f"   Обновлено плагинов: {updated_plugins}")
        print(f"   Хешей обновлено: {hashes_updated}")
        print(f"   Пропущено (уже есть метаданные): {skipped_count}")
        print(f"   Файлы не найдены: {not_found_count}")
        print(f"   Метаданные не найдены в файлах: {no_metadata_count}")

        return True

    except FileNotFoundError as e:
        print(f"❌ Файл store.json не найден: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return False
    except IOError as e:
        print(f"❌ Ошибка при работе с файлом store.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при обновлении store.json: {type(e).__name__}: {e}")
        return False
