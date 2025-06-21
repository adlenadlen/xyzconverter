import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Label, Button, Frame, StringVar
from tkinterdnd2 import DND_FILES, TkinterDnD
import os


# ----------------------------------------------------------------------
# РАЗДЕЛ 1: ФУНКЦИИ ПАРСИНГА И ФОРМАТИРОВАНИЯ
# ----------------------------------------------------------------------

def read_file_with_fallback_encoding(filepath: str) -> str:
    """Читает файл, пробуя несколько кодировок (UTF-8, затем ANSI/cp1251)."""
    encodings_to_try = ['utf-8', 'cp1251']
    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise IOError(
        f"Не удалось прочитать файл '{os.path.basename(filepath)}'. Файл имеет неизвестную или поврежденную кодировку.")


def parse_sdr33(sdr_content: str) -> list[dict]:
    lines = sdr_content.strip().split('\n')
    if not lines: return []
    header = lines[0]
    if len(header) < 45 or not header.startswith("00NMSDR33"): raise ValueError("Неверный заголовок SDR33.")
    order_flag = header[44]
    if order_flag not in ('1', '2'): raise ValueError(f"Неверный флаг порядка координат: '{order_flag}'.")

    points_data = []
    for line in lines[1:]:
        if len(line) >= 84 and line.startswith(('08', '02')):
            coord1_str, coord2_str = line[20:36].strip(), line[36:52].strip()
            point_dict = {
                'point': line[4:20].strip(),
                'height': float(line[52:68].strip()),
                'description': line[68:84].strip()
            }
            if order_flag == '1':  # Север, Восток
                point_dict['north'], point_dict['east'] = float(coord1_str), float(coord2_str)
            else:  # Восток, Север
                point_dict['east'], point_dict['north'] = float(coord1_str), float(coord2_str)
            points_data.append(point_dict)
    return points_data


def parse_txt_generic(file_content: str, delimiter: str, order_map: dict) -> list[dict]:
    points_data = []
    for line_num, line in enumerate(file_content.strip().split('\n'), 1):
        if not line.strip(): continue
        try:
            parts = [p.strip() for p in line.split(delimiter)]
            if len(parts) < 4: continue

            point_dict = {
                'point': parts[order_map['P']], 'north': float(parts[order_map['N']]),
                'east': float(parts[order_map['E']]), 'height': float(parts[order_map['H']]),
                'description': parts[order_map['D']] if len(parts) > 4 else ""
            }
            points_data.append(point_dict)
        except (ValueError, IndexError):
            print(f"Предупреждение: Пропущена строка {line_num} из-за неверного формата.")
            continue
    return points_data


def format_to_sdr33(points_data: list[dict]) -> str:
    header = "00NMSDR33 V04-02.00                     111111"
    point_lines = [
        (f"08KI{p['point']:>16}{p['north']:<16.4f}{p['east']:<16.4f}{p['height']:<16.4f}{p['description']:<16}")[:84]
        for p in points_data]
    return "\n".join([header] + point_lines)


def format_to_txt_generic(points_data: list[dict], delimiter: str, order: str) -> str:
    lines = []
    for p in points_data:
        if order == "NE":  # Север, Восток
            line = f"{p['point']}{delimiter}{p['north']}{delimiter}{p['east']}{delimiter}{p['height']}{delimiter}{p['description']}"
        else:  # Восток, Север
            line = f"{p['point']}{delimiter}{p['east']}{delimiter}{p['north']}{delimiter}{p['height']}{delimiter}{p['description']}"
        lines.append(line)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# РАЗДЕЛ 2: ГРАФИЧЕСКИЙ ИНТЕРФЕЙС И ЛОГИКА
# ----------------------------------------------------------------------

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Adlen's xyzconverter")
        self.geometry("480x480")
        self.resizable(False, False)

        self.filepath = None
        self.parsed_data = None
        self.ORDER_OPTIONS = ['Север, Восток', 'Восток, Север']

        self.input_delimiter_var = StringVar()
        self.input_order_var = StringVar()
        self.output_format_var = StringVar()
        self.output_delimiter_var = StringVar()
        self.output_order_var = StringVar()

        self.file_frame = Frame(self)
        self.file_frame.pack(pady=10, padx=10, fill="x")
        self.file_label = Label(self.file_frame, text="Перетащите файл сюда", bg="lightgrey", relief="solid", height=4)
        self.file_label.pack(fill="x")
        self.file_label.drop_target_register(DND_FILES)
        self.file_label.dnd_bind('<<Drop>>', self.handle_drop)
        Button(self.file_frame, text="... или выберите файл", command=self.select_file).pack(pady=5)

        self.input_options_frame = ttk.LabelFrame(self, text=" 1. Параметры импорта (входной файл) ")
        self.input_options_frame.pack(pady=5, padx=10, fill="x")
        Label(self.input_options_frame, text="Выберите файл для настройки параметров").pack(pady=10)

        self.output_options_frame = ttk.LabelFrame(self, text=" 2. Параметры экспорта (выходной файл) ")
        self.output_options_frame.pack(pady=5, padx=10, fill="x")
        Label(self.output_options_frame, text="Выберите файл для настройки параметров").pack(pady=10)

        self.convert_button = Button(self, text="Конвертировать", command=self.start_conversion, state="disabled",
                                     font=("Arial", 12, "bold"))
        self.convert_button.pack(pady=15)

    def handle_drop(self, event):
        self.load_file(event.data.strip('{}'))

    def select_file(self):
        fp = filedialog.askopenfilename(
            filetypes=[("Все поддерживаемые", "*.sdr *.txt *.pnt *.csv"), ("All files", "*.*")])
        if fp: self.load_file(fp)

    def load_file(self, filepath):
        self.filepath = filepath
        self.file_label.config(text=os.path.basename(filepath), bg="lightblue")
        self.update_ui()
        self.convert_button.config(state="normal")

    def update_ui(self):
        for w in self.input_options_frame.winfo_children(): w.destroy()
        for w in self.output_options_frame.winfo_children(): w.destroy()
        _, extension = os.path.splitext(self.filepath);
        extension = extension.lower()

        # ИЗМЕНЕНИЕ: Разделена логика для TXT и CSV
        if extension == '.sdr':
            Label(self.input_options_frame, text="Формат SDR33 определен автоматически.").pack(pady=10)
        elif extension == '.pnt':
            Label(self.input_options_frame, text="Формат PNT (Разделитель: ',', Порядок: Восток, Север)").pack(pady=10)
        elif extension == '.csv':
            grid = Frame(self.input_options_frame);
            grid.pack(pady=10, padx=5)
            Label(grid, text="Разделитель:").grid(row=0, column=0, sticky="w", padx=5)
            Label(grid, text="Точка с запятой (;)").grid(row=0, column=1, sticky="w")

            Label(grid, text="Порядок координат:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            cb_ord = ttk.Combobox(grid, textvariable=self.input_order_var, values=self.ORDER_OPTIONS, state="readonly")
            cb_ord.grid(row=1, column=1, sticky="ew")
            cb_ord.set(self.ORDER_OPTIONS[0])
        elif extension == '.txt':
            grid = Frame(self.input_options_frame);
            grid.pack(pady=10, padx=5)
            Label(grid, text="Разделитель:").grid(row=0, column=0, sticky="w", padx=5)
            delimiters = ['Запятая', 'Пробел', 'Табуляция', 'Точка с запятой']
            cb_del = ttk.Combobox(grid, textvariable=self.input_delimiter_var, values=delimiters, state="readonly")
            cb_del.grid(row=0, column=1, sticky="ew")
            cb_del.set('Запятая')

            Label(grid, text="Порядок координат:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            cb_ord = ttk.Combobox(grid, textvariable=self.input_order_var, values=self.ORDER_OPTIONS, state="readonly")
            cb_ord.grid(row=1, column=1, sticky="ew")
            cb_ord.set(self.ORDER_OPTIONS[0])

        all_formats = ['SDR', 'TXT', 'PNT', 'CSV']
        format_map = {'.sdr': 'SDR', '.txt': 'TXT', '.pnt': 'PNT', '.csv': 'CSV'}
        input_format_name = format_map.get(extension)
        filtered_output_formats = [f for f in all_formats if f != input_format_name]

        grid_out = Frame(self.output_options_frame);
        grid_out.pack(pady=10, padx=5)
        Label(grid_out, text="Формат вывода:").grid(row=0, column=0, sticky="w", padx=5)
        cb_out_format = ttk.Combobox(grid_out, textvariable=self.output_format_var, values=filtered_output_formats,
                                     state="readonly")
        cb_out_format.grid(row=0, column=1, sticky="ew")
        if filtered_output_formats: cb_out_format.set(filtered_output_formats[0])
        cb_out_format.bind("<<ComboboxSelected>>", self.update_output_sub_options)

        self.output_sub_options_frame = Frame(self.output_options_frame)
        self.output_sub_options_frame.pack(pady=5, padx=10, fill="x")
        self.update_output_sub_options()

    def update_output_sub_options(self, event=None):
        for w in self.output_sub_options_frame.winfo_children(): w.destroy()
        out_format = self.output_format_var.get()
        if not out_format: return

        if out_format == "SDR":
            Label(self.output_sub_options_frame, text="Стандартный формат SDR33.").pack()
        elif out_format == "PNT":
            Label(self.output_sub_options_frame, text="Формат PNT (Разделитель: ',', Порядок: Восток, Север)").pack()
        elif out_format in ["TXT", "CSV"]:
            grid = Frame(self.output_sub_options_frame);
            grid.pack()
            Label(grid, text="Разделитель:").grid(row=0, column=0, padx=5, sticky="w")
            delimiters = ['Запятая', 'Пробел', 'Табуляция', 'Точка с запятой']
            cb_del = ttk.Combobox(grid, textvariable=self.output_delimiter_var, values=delimiters, state="readonly")
            cb_del.grid(row=0, column=1, sticky="ew")
            cb_del.set('Точка с запятой' if out_format == 'CSV' else 'Запятая')
            if out_format == 'CSV': cb_del.config(state="disabled")

            Label(grid, text="Порядок координат:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            cb_ord = ttk.Combobox(grid, textvariable=self.output_order_var, values=self.ORDER_OPTIONS, state="readonly")
            cb_ord.grid(row=1, column=1, sticky="ew")
            cb_ord.set(self.ORDER_OPTIONS[0])

    def start_conversion(self):
        if not self.filepath: return
        try:
            content = read_file_with_fallback_encoding(self.filepath)
            _, extension = os.path.splitext(self.filepath);
            extension = extension.lower()

            # ИЗМЕНЕНИЕ: Разделена логика парсинга для TXT и CSV
            if extension == '.sdr':
                points_data = parse_sdr33(content)
            elif extension == '.pnt':
                points_data = parse_txt_generic(content, ',', {'P': 0, 'E': 1, 'N': 2, 'H': 3, 'D': 4})
            elif extension == '.csv':
                delimiter = ';'
                order_map = {'P': 0, 'N': 1, 'E': 2, 'H': 3, 'D': 4} if 'Север' in self.input_order_var.get() else {
                    'P': 0, 'E': 1, 'N': 2, 'H': 3, 'D': 4}
                points_data = parse_txt_generic(content, delimiter, order_map)
            elif extension == '.txt':
                delim_map = {'Запятая': ',', 'Пробел': ' ', 'Табуляция': '\t', 'Точка с запятой': ';'}
                delimiter = delim_map[self.input_delimiter_var.get()]
                order_map = {'P': 0, 'N': 1, 'E': 2, 'H': 3, 'D': 4} if 'Север' in self.input_order_var.get() else {
                    'P': 0, 'E': 1, 'N': 2, 'H': 3, 'D': 4}
                points_data = parse_txt_generic(content, delimiter, order_map)

            if not points_data: raise ValueError("Входной файл пуст или не содержит корректных данных.")

            output_format = self.output_format_var.get()
            if not output_format: raise ValueError("Формат вывода не выбран.")

            if output_format == "SDR":
                result_content, output_ext = format_to_sdr33(points_data), '.sdr'
            elif output_format == "PNT":
                result_content, output_ext = format_to_txt_generic(points_data, ',', 'EN'), '.pnt'
            else:  # TXT или CSV
                delim_map = {'Запятая': ',', 'Пробел': ' ', 'Табуляция': '\t', 'Точка с запятой': ';'}
                delimiter = delim_map[self.output_delimiter_var.get()]
                order = 'NE' if 'Север' in self.output_order_var.get() else 'EN'
                result_content = format_to_txt_generic(points_data, delimiter, order)
                output_ext = '.csv' if output_format == 'CSV' else '.txt'

            output_path = os.path.splitext(self.filepath)[0] + "_converted" + output_ext
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result_content)

            messagebox.showinfo("Успех", f"Файл успешно сохранен как:\n{output_path}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка:\n{str(e)}")
        finally:
            self.reset_ui()

    def reset_ui(self):
        self.filepath = None
        self.file_label.config(text="Перетащите файл сюда", bg="lightgrey")
        self.convert_button.config(state="disabled")
        for w in self.input_options_frame.winfo_children(): w.destroy()
        for w in self.output_options_frame.winfo_children(): w.destroy()
        Label(self.input_options_frame, text="Выберите файл для настройки параметров").pack(pady=10)
        Label(self.output_options_frame, text="Выберите файл для настройки параметров").pack(pady=10)


if __name__ == "__main__":
    app = App()
    app.mainloop()
