import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import webbrowser
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


# ----------------------------------------------------------------------
# РАЗДЕЛ 1: КОНСТАНТЫ И ТИПЫ ДАННЫХ
# ----------------------------------------------------------------------

class Delimiter(Enum):
    COMMA = (',', 'Запятая')
    SPACE = (' ', 'Пробел')
    TAB = ('\t', 'Табуляция')
    SEMICOLON = (';', 'Точка с запятой')

    @property
    def char(self) -> str:
        return self.value[0]

    @property
    def display_name(self) -> str:
        return self.value[1]

    @classmethod
    def from_display_name(cls, name: str) -> 'Delimiter':
        for delimiter in cls:
            if delimiter.display_name == name:
                return delimiter
        raise ValueError(f"Unknown delimiter: {name}")


class CoordinateOrder(Enum):
    NORTH_EAST = ('NE', 'Север, Восток')
    EAST_NORTH = ('EN', 'Восток, Север')

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def display_name(self) -> str:
        return self.value[1]

    @classmethod
    def from_display_name(cls, name: str) -> 'CoordinateOrder':
        for order in cls:
            if order.display_name == name:
                return order
        raise ValueError(f"Unknown order: {name}")


@dataclass
class Point:
    """Структура данных для точки"""
    point: str
    north: float
    east: float
    height: float
    description: str = ""

    def to_dict(self) -> Dict[str, any]:
        return {
            'point': self.point,
            'north': self.north,
            'east': self.east,
            'height': self.height,
            'description': self.description
        }


# ----------------------------------------------------------------------
# РАЗДЕЛ 2: ФУНКЦИИ ПАРСИНГА И ФОРМАТИРОВАНИЯ
# ----------------------------------------------------------------------

class FileReader:
    """Класс для чтения файлов с различными кодировками"""
    ENCODINGS = ['utf-8', 'cp1251', 'cp1252', 'latin-1']

    @classmethod
    def read_file(cls, filepath: str) -> str:
        """Читает файл, пробуя несколько кодировок."""
        for encoding in cls.ENCODINGS:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        filename = os.path.basename(filepath)
        raise IOError(
            f"Не удалось прочитать файл '{filename}'. "
            f"Файл имеет неизвестную или поврежденную кодировку."
        )


class SDR33Parser:
    """Парсер для формата SDR33"""
    HEADER_PREFIX = "00NMSDR33"
    MIN_HEADER_LENGTH = 45
    VALID_ORDER_FLAGS = {'1', '2'}
    POINT_PREFIXES = {'08', '02'}
    MIN_LINE_LENGTH = 84

    @classmethod
    def parse(cls, content: str) -> List[Point]:
        lines = content.strip().split('\n')
        if not lines:
            return []

        header = lines[0]
        cls._validate_header(header)

        order_flag = header[44]
        points = []

        for line_num, line in enumerate(lines[1:], 2):
            if len(line) >= cls.MIN_LINE_LENGTH and line[:2] in cls.POINT_PREFIXES:
                try:
                    point = cls._parse_line(line, order_flag)
                    points.append(point)
                except ValueError as e:
                    print(f"Предупреждение: Строка {line_num}: {e}")
                    continue

        return points

    @classmethod
    def _validate_header(cls, header: str) -> None:
        if len(header) < cls.MIN_HEADER_LENGTH:
            raise ValueError(f"Заголовок SDR33 слишком короткий: {len(header)} < {cls.MIN_HEADER_LENGTH}")

        if not header.startswith(cls.HEADER_PREFIX):
            raise ValueError(f"Неверный заголовок SDR33: не начинается с '{cls.HEADER_PREFIX}'")

        order_flag = header[44]
        if order_flag not in cls.VALID_ORDER_FLAGS:
            raise ValueError(f"Неверный флаг порядка координат: '{order_flag}'")

    @classmethod
    def _parse_line(cls, line: str, order_flag: str) -> Point:
        point_name = line[4:20].strip()
        coord1 = float(line[20:36].strip())
        coord2 = float(line[36:52].strip())
        height = float(line[52:68].strip())
        description = line[68:84].strip() if len(line) >= 84 else ""

        if order_flag == '1':  # Север, Восток
            north, east = coord1, coord2
        else:  # Восток, Север
            north, east = coord2, coord1

        return Point(point_name, north, east, height, description)


class GenericTextParser:
    """Парсер для текстовых форматов (TXT, CSV, PNT)"""

    @classmethod
    def parse(cls, content: str, delimiter: str, order: CoordinateOrder) -> List[Point]:
        points = []

        for line_num, line in enumerate(content.strip().split('\n'), 1):
            line = line.strip()
            if not line:
                continue

            try:
                point = cls._parse_line(line, delimiter, order)
                points.append(point)
            except (ValueError, IndexError) as e:
                print(f"Предупреждение: Строка {line_num} пропущена: {e}")
                continue

        return points

    @classmethod
    def _parse_line(cls, line: str, delimiter: str, order: CoordinateOrder) -> Point:
        parts = [p.strip() for p in line.split(delimiter)]

        if len(parts) < 4:
            raise ValueError(f"Недостаточно полей: {len(parts)} < 4")

        point_name = parts[0]
        description = parts[4] if len(parts) > 4 else ""

        if order == CoordinateOrder.NORTH_EAST:
            north = float(parts[1])
            east = float(parts[2])
        else:  # EAST_NORTH
            east = float(parts[1])
            north = float(parts[2])

        height = float(parts[3])

        return Point(point_name, north, east, height, description)


class FileFormatter:
    """Класс для форматирования данных в различные форматы"""

    @staticmethod
    def to_sdr33(points: List[Point]) -> str:
        header = "00NMSDR33 V04-02.00                     111111"
        lines = [header]

        for point in points:
            # Форматирование с выравниванием полей
            line = (
                       f"08KI{point.point:>16}"
                       f"{point.north:<16.4f}"
                       f"{point.east:<16.4f}"
                       f"{point.height:<16.4f}"
                       f"{point.description:<16}"
                   )[:84]  # Обрезка до 84 символов
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def to_text(points: List[Point], delimiter: str, order: CoordinateOrder) -> str:
        lines = []

        for point in points:
            if order == CoordinateOrder.NORTH_EAST:
                parts = [
                    point.point,
                    f"{point.north:.4f}",
                    f"{point.east:.4f}",
                    f"{point.height:.4f}",
                    point.description
                ]
            else:  # EAST_NORTH
                parts = [
                    point.point,
                    f"{point.east:.4f}",
                    f"{point.north:.4f}",
                    f"{point.height:.4f}",
                    point.description
                ]

            lines.append(delimiter.join(parts))

        return "\n".join(lines)


# ----------------------------------------------------------------------
# РАЗДЕЛ 3: ГРАФИЧЕСКИЙ ИНТЕРФЕЙС
# ----------------------------------------------------------------------

class ConverterApp(TkinterDnD.Tk):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._init_variables()
        self._create_widgets()

    def _setup_window(self):
        """Настройка параметров окна"""
        self.title("xyzconverter")
        self.geometry("240x400")
        self.resizable(False, False)

        # Центрирование окна
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _init_variables(self):
        """Инициализация переменных"""
        self.filepath: Optional[str] = None
        self.parsed_data: Optional[List[Point]] = None

        self.input_delimiter_var = tk.StringVar()
        self.input_order_var = tk.StringVar()
        self.output_format_var = tk.StringVar()
        self.output_delimiter_var = tk.StringVar()
        self.output_order_var = tk.StringVar()

        self.output_format_var.trace('w', self._on_output_format_changed)

    def _create_widgets(self):
        """Создание виджетов интерфейса"""
        # Фрейм для выбора файла
        self.file_frame = ttk.Frame(self)
        self.file_frame.pack(pady=10, padx=10, fill="x")

        # Создаем Label для drag-and-drop без tkinter.Label синтаксиса
        self.file_label = tk.Label(
            self.file_frame,
            text="Перетащите файл сюда",
            bg="lightgrey",
            relief="solid",
            height=3,
            cursor="hand2"
        )
        self.file_label.pack(fill="x", padx=5, pady=5)

        # Настройка drag and drop
        self.file_label.drop_target_register(DND_FILES)
        self.file_label.dnd_bind('<<Drop>>', self._handle_drop)

        self.select_button = ttk.Button(
            self.file_frame,
            text="... или выберите файл",
            command=self._select_file
        )
        self.select_button.pack(pady=5)

        # Фрейм параметров импорта
        self.input_frame = ttk.LabelFrame(
            self,
            text=" 1. Параметры импорта",
            padding=5
        )
        self.input_frame.pack(pady=5, padx=5, fill="x")

        self.input_placeholder = ttk.Label(
            self.input_frame,
            text="Выберите файл"
        )
        self.input_placeholder.pack()

        # Фрейм параметров экспорта
        self.output_frame = ttk.LabelFrame(
            self,
            text=" 2. Параметры экспорта",
            padding=5
        )
        self.output_frame.pack(pady=5, padx=5, fill="x")

        self.output_placeholder = ttk.Label(
            self.output_frame,
            text="Выберите файл"
        )
        self.output_placeholder.pack()

        # Кнопка конвертации
        self.convert_button = ttk.Button(
            self,
            text="Конвертировать",
            command=self._convert,
            state="disabled",
            style="Accent.TButton"
        )
        self.convert_button.pack(pady=2)

        # Настройка стиля для кнопки
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 12, "bold"))

        # Фрейм для ссылки на GitHub
        self.footer_frame = ttk.Frame(self)
        self.footer_frame.pack(side="bottom", pady=5)

        # Ссылка на GitHub
        self.github_link = tk.Label(
            self.footer_frame,
            text="версия 1.0.2",
            fg="blue",
            cursor="hand2",
            font=("Arial", 10, "underline")
        )
        self.github_link.pack()
        self.github_link.bind("<Button-1>", self._open_github)

        # Подсказка при наведении
        self.github_link.bind("<Enter>", lambda e: self.github_link.config(fg="darkblue"))
        self.github_link.bind("<Leave>", lambda e: self.github_link.config(fg="blue"))

    def _open_github(self, event):
        """Открытие ссылки на GitHub в браузере"""
        webbrowser.open("https://github.com/adlenadlen/xyzconverter/releases/latest")

    def _handle_drop(self, event):
        """Обработка перетаскивания файла"""
        filepath = event.data.strip('{}')
        self._load_file(filepath)

    def _select_file(self):
        """Выбор файла через диалог"""
        filetypes = [
            ("Поддерживаемые форматы", "*.sdr;*.txt;*.pnt;*.csv"),
            ("SDR файлы", "*.sdr"),
            ("Текстовые файлы", "*.txt"),
            ("PNT файлы", "*.pnt"),
            ("CSV файлы", "*.csv"),
            ("Все файлы", "*.*")
        ]

        filepath = filedialog.askopenfilename(
            title="Выберите файл для конвертации",
            filetypes=filetypes
        )

        if filepath:
            self._load_file(filepath)

    def _load_file(self, filepath: str):
        """Загрузка файла и обновление интерфейса"""
        if not os.path.exists(filepath):
            messagebox.showerror("Ошибка", f"Файл не существует: {filepath}")
            return

        self.filepath = filepath
        filename = os.path.basename(filepath)

        # Обновление метки файла
        self.file_label.config(
            text=f"📄 {filename}",
            bg="lightblue"
        )

        # Обновление интерфейса
        self._update_ui()
        self.convert_button.config(state="normal")

    def _update_ui(self):
        """Обновление интерфейса в зависимости от типа файла"""
        if not self.filepath:
            return

        # Очистка фреймов
        for widget in self.input_frame.winfo_children():
            widget.destroy()
        for widget in self.output_frame.winfo_children():
            widget.destroy()

        # Определение расширения файла
        _, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        # Настройка параметров импорта
        self._setup_input_options(ext)

        # Настройка параметров экспорта
        self._setup_output_options(ext)

    def _setup_input_options(self, extension: str):
        """Настройка параметров импорта"""
        if extension == '.sdr':
            ttk.Label(
                self.input_frame,
                text="✓ Стандартный формат SDR"
            ).pack()

        elif extension == '.pnt':
            ttk.Label(
                self.input_frame,
                text="✓ Стандартный формат PNT"
            ).pack()

        elif extension == '.csv':
            self._create_csv_input_options()

        elif extension == '.txt':
            self._create_txt_input_options()

        else:
            ttk.Label(
                self.input_frame,
                text="⚠ Недопустимый формат!"
            ).pack()
            self._create_txt_input_options()

    def _create_csv_input_options(self):
        """Создание опций для CSV файлов"""
        frame = ttk.Frame(self.input_frame)
        frame.pack(fill="x", padx=5)

        # Разделитель (фиксированный для CSV)
        ttk.Label(frame, text="Разделитель:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frame, text="Точка с запятой (;)").grid(row=0, column=1, sticky="w", pady=2)

        # Порядок координат
        ttk.Label(frame, text="Порядок:").grid(row=1, column=0, sticky="w", pady=2)

        order_combo = ttk.Combobox(
            frame,
            textvariable=self.input_order_var,
            values=[order.display_name for order in CoordinateOrder],
            state="readonly",
            width=20
        )
        order_combo.grid(row=1, column=1, sticky="ew", pady=2)
        order_combo.set(CoordinateOrder.NORTH_EAST.display_name)

        frame.columnconfigure(1, weight=1)

    def _create_txt_input_options(self):
        """Создание опций для TXT файлов"""
        frame = ttk.Frame(self.input_frame)
        frame.pack(fill="x", padx=5)

        # Разделитель
        ttk.Label(frame, text="Разделитель:").grid(row=0, column=0, sticky="w", pady=2)

        delimiter_combo = ttk.Combobox(
            frame,
            textvariable=self.input_delimiter_var,
            values=[d.display_name for d in Delimiter],
            state="readonly",
            width=20
        )
        delimiter_combo.grid(row=0, column=1, sticky="ew", pady=2)
        delimiter_combo.set(Delimiter.COMMA.display_name)

        # Порядок координат
        ttk.Label(frame, text="Порядок:").grid(row=1, column=0, sticky="w", pady=2)

        order_combo = ttk.Combobox(
            frame,
            textvariable=self.input_order_var,
            values=[order.display_name for order in CoordinateOrder],
            state="readonly",
            width=20
        )
        order_combo.grid(row=1, column=1, sticky="ew", pady=2)
        order_combo.set(CoordinateOrder.NORTH_EAST.display_name)

        frame.columnconfigure(1, weight=1)

    def _setup_output_options(self, input_extension: str):
        """Настройка параметров экспорта"""
        # Определение доступных форматов
        format_map = {
            '.sdr': 'SDR',
            '.txt': 'TXT',
            '.pnt': 'PNT',
            '.csv': 'CSV'
        }

        input_format = format_map.get(input_extension, 'TXT')
        available_formats = [fmt for fmt in format_map.values() if fmt != input_format]

        # Создание выбора формата
        frame = ttk.Frame(self.output_frame)
        frame.pack(fill="x", padx=5)

        ttk.Label(frame, text="Формат:").grid(row=0, column=0, sticky="w", pady=2)

        format_combo = ttk.Combobox(
            frame,
            textvariable=self.output_format_var,
            values=available_formats,
            state="readonly",
            width=20
        )
        format_combo.grid(row=0, column=1, sticky="ew", pady=2)

        if available_formats:
            format_combo.set(available_formats[0])

        frame.columnconfigure(1, weight=1)

        # Фрейм для дополнительных опций
        self.output_sub_frame = ttk.Frame(self.output_frame)
        self.output_sub_frame.pack(fill="x", padx=5, pady=(5, 0))

        # Обновление дополнительных опций
        self._update_output_sub_options()

    def _on_output_format_changed(self, *args):
        """Обработчик изменения формата вывода"""
        # args не используется, но необходим для trace callback
        self._update_output_sub_options()

    def _update_output_sub_options(self):
        """Обновление дополнительных опций экспорта"""
        # Очистка фрейма
        for widget in self.output_sub_frame.winfo_children():
            widget.destroy()

        output_format = self.output_format_var.get()
        if not output_format:
            return

        if output_format == 'SDR':
            ttk.Label(
                self.output_sub_frame,
                text="✓ Стандартный формат SDR33"
            ).pack()

        elif output_format == 'PNT':
            ttk.Label(
                self.output_sub_frame,
                text="✓ Стандартный формат PNT"
            ).pack()

        elif output_format in ['TXT', 'CSV']:
            self._create_text_output_options(output_format)

    def _create_text_output_options(self, format_type: str):
        """Создание опций для текстового вывода"""
        frame = ttk.Frame(self.output_sub_frame)
        frame.pack(fill="x")

        # Разделитель
        ttk.Label(frame, text="Разделитель:").grid(row=0, column=0, sticky="w", pady=2)

        if format_type == 'CSV':
            # Для CSV фиксированный разделитель
            ttk.Label(frame, text="Точка с запятой (;)").grid(row=0, column=1, sticky="w", pady=2)
            self.output_delimiter_var.set(Delimiter.SEMICOLON.display_name)
        else:
            # Для TXT выбор разделителя
            delimiter_combo = ttk.Combobox(
                frame,
                textvariable=self.output_delimiter_var,
                values=[d.display_name for d in Delimiter],
                state="readonly",
                width=20
            )
            delimiter_combo.grid(row=0, column=1, sticky="ew", pady=2)
            delimiter_combo.set(Delimiter.COMMA.display_name)

        # Порядок координат
        ttk.Label(frame, text="Порядок:").grid(row=1, column=0, sticky="w", pady=2)

        order_combo = ttk.Combobox(
            frame,
            textvariable=self.output_order_var,
            values=[order.display_name for order in CoordinateOrder],
            state="readonly",
            width=20
        )
        order_combo.grid(row=1, column=1, sticky="ew", pady=2)
        order_combo.set(CoordinateOrder.NORTH_EAST.display_name)

        frame.columnconfigure(1, weight=1)

    def _convert(self):
        """Выполнение конвертации"""
        if not self.filepath:
            return

        try:
            # Чтение файла
            content = FileReader.read_file(self.filepath)

            # Парсинг данных
            points = self._parse_input_file(content)

            if not points:
                raise ValueError("Входной файл пуст или не содержит корректных данных")

            # Форматирование данных
            output_content = self._format_output_data(points)

            # Сохранение файла
            output_path = self._save_output_file(output_content)

            # Показ сообщения об успехе
            messagebox.showinfo(
                "Успех",
                f"Файл успешно сконвертирован!\n\n"
                f"Обработано точек: {len(points)}\n"
                f"Сохранено в: {os.path.basename(output_path)}"
            )

        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Произошла ошибка при конвертации:\n\n{str(e)}"
            )

        finally:
            self._reset_ui()

    def _parse_input_file(self, content: str) -> List[Point]:
        """Парсинг входного файла"""
        _, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext == '.sdr':
            return SDR33Parser.parse(content)

        elif ext == '.pnt':
            return GenericTextParser.parse(
                content,
                Delimiter.COMMA.char,
                CoordinateOrder.EAST_NORTH
            )

        elif ext == '.csv':
            order = CoordinateOrder.from_display_name(self.input_order_var.get())
            return GenericTextParser.parse(
                content,
                Delimiter.SEMICOLON.char,
                order
            )

        else:  # .txt или другое
            delimiter = Delimiter.from_display_name(self.input_delimiter_var.get())
            order = CoordinateOrder.from_display_name(self.input_order_var.get())
            return GenericTextParser.parse(content, delimiter.char, order)

    def _format_output_data(self, points: List[Point]) -> str:
        """Форматирование данных для вывода"""
        output_format = self.output_format_var.get()

        if output_format == 'SDR':
            return FileFormatter.to_sdr33(points)

        elif output_format == 'PNT':
            return FileFormatter.to_text(
                points,
                Delimiter.COMMA.char,
                CoordinateOrder.EAST_NORTH
            )

        elif output_format == 'CSV':
            order = CoordinateOrder.from_display_name(self.output_order_var.get())
            return FileFormatter.to_text(
                points,
                Delimiter.SEMICOLON.char,
                order
            )

        else:  # TXT
            delimiter = Delimiter.from_display_name(self.output_delimiter_var.get())
            order = CoordinateOrder.from_display_name(self.output_order_var.get())
            return FileFormatter.to_text(points, delimiter.char, order)

    def _save_output_file(self, content: str) -> str:
        """Сохранение выходного файла"""
        # Определение расширения
        output_format = self.output_format_var.get()
        extension_map = {
            'SDR': '.sdr',
            'TXT': '.txt',
            'PNT': '.pnt',
            'CSV': '.csv'
        }
        output_ext = extension_map.get(output_format, '.txt')

        # Формирование пути
        base_name = os.path.splitext(self.filepath)[0]
        output_path = f"{base_name}_converted{output_ext}"

        # Проверка существования файла
        if os.path.exists(output_path):
            counter = 1
            while os.path.exists(f"{base_name}_converted_{counter}{output_ext}"):
                counter += 1
            output_path = f"{base_name}_converted_{counter}{output_ext}"

        # Сохранение
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    def _reset_ui(self):
        """Сброс интерфейса к начальному состоянию"""
        self.filepath = None
        self.parsed_data = None

        # Сброс метки файла
        self.file_label.config(
            text="Перетащите файл сюда",
            bg="lightgrey"
        )

        # Отключение кнопки
        self.convert_button.config(state="disabled")

        # Очистка фреймов
        for widget in self.input_frame.winfo_children():
            widget.destroy()
        for widget in self.output_frame.winfo_children():
            widget.destroy()

        # Восстановление заглушек
        ttk.Label(
            self.input_frame,
            text="Выберите файл для настройки параметров"
        ).pack()

        ttk.Label(
            self.output_frame,
            text="Выберите файл для настройки параметров"
        ).pack()


# ----------------------------------------------------------------------
# РАЗДЕЛ 4: ТОЧКА ВХОДА
# ----------------------------------------------------------------------

def main():
    """Главная функция запуска приложения"""
    try:
        app = ConverterApp()
        app.mainloop()
    except Exception as e:
        messagebox.showerror(
            "Критическая ошибка",
            f"Произошла критическая ошибка:\n\n{str(e)}"
        )
        raise


if __name__ == "__main__":
    main()
