import customtkinter as ctk
import matplotlib.pyplot as plt
from tkinter import filedialog
from functools import partial
from logAnalyser import detect_heater_zones, get_file, consol_controller, extract_all_zones_all_series_limited
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Tuna 분석기")
root.geometry("1000x900")

selected_temp_cmode = ctk.StringVar()
selected_etype = ctk.StringVar()

data_rows = []
result_table_labels = []
zone_data_global = {}
header_zone_buttons = []

def upload_and_process():
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if file_path:
        file_path_label.configure(
            text=file_path,
            text_color="#00cc00",
            font=("Segoe UI", 13, "bold", "italic")
        )
        global data_rows
        data_rows = get_file(file_path)

def plot_single_zone(zone_name):
    print(f"Clicked zone: {zone_name}")
    print(f"Available keys: {list(zone_data_global.keys())}")

    zone_key = zone_name.upper()  # ← 대문자로 변환해서 매칭

    if zone_key not in zone_data_global:
        print("Zone not matched in data!")
        return

    x, sp, spike, profile = zone_data_global[zone_key]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, sp, label="SP", linewidth=1.5)
    ax.plot(x, spike, label="Spike", linewidth=1.5)
    ax.plot(x, profile, label="Profile", linewidth=1.5)

    ax.set_title(zone_key)
    ax.grid(True)
    ax.legend(fontsize=8)
    ax.set_xlabel("Time")
    ax.set_ylabel("Temp (°C)")

    for widget in graph_frame.winfo_children():
        widget.destroy()

    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.draw()
    canvas.get_tk_widget().pack()

    plt.close(fig)

def create_zone_header_buttons(table_frame, headers):
    global header_zone_buttons
    for btn in header_zone_buttons:
        btn.destroy()
    header_zone_buttons.clear()

    table_frame.update_idletasks()

    for col_idx, header_text in enumerate(headers):
        if header_text.startswith("Zone"):
            zone_name = header_text  # ex: "Zone1", ...

            # 기존 헤더 텍스트 대신 라벨 생성 + 클릭 + hover 스타일
            label = ctk.CTkLabel(
                master=table_frame,
                text=zone_name,
                width=60,
                height=35,
                fg_color="#eeeeee",  # 헤더 배경과 통일
                text_color="black",
                font=("Segoe UI", 12, "bold"),
                cursor="hand2"
            )
            label.grid(row=0, column=col_idx, padx=(0 if col_idx == 0 else 1), pady=0, sticky="nsew")
            label.bind("<Button-1>", lambda e, z=zone_name.upper(): plot_single_zone(z))

            header_zone_buttons.append(label)

def run_analysis():
    global zone_data_global

    if not data_rows:
        result_label.configure(text="CSV 파일을 먼저 업로드하세요.", text_color="#cc0000", font=("Segoe UI", 13, "bold", "italic"))
        return

    zone_count = detect_heater_zones(data_rows[0])
    temp_cmode = selected_temp_cmode.get()
    etype = selected_etype.get()

    if not temp_cmode or not etype:
        result_label.configure(text="모든 값을 입력하고 CSV를 업로드하세요.", text_color="#cc0000", font=("Segoe UI", 13, "bold", "italic"))
        return

    p1, initial_p2, p2, recipe_step = consol_controller(temp_cmode, etype, data_rows)
    result_label.configure(text="분석 완료! (Zone 헤더 클릭으로 그래프 확인 가능)", text_color="#00cc00", font=("Segoe UI", 13, "bold", "italic"))

    for label in result_table_labels:
        label.destroy()
    result_table_labels.clear()

    headers = ["구분"] + [f"Zone{i+1}" for i in range(zone_count)] + ["비고"]
    rows = [
        ["초기 P2"] + initial_p2 + ["※ 첫 튜닝시에 적용"],
        ["P1 조정"] + p1 + [""],
        ["P2 조정"] + p2 + [""]
    ]

    header_font = ("Segoe UI", 12, "bold")
    cell_font = ("Segoe UI", 14)
    header_bg = "#eeeeee"
    cell_bg = "#ffffff"
    border_color = "#cccccc"

    for widget in result_frame.winfo_children():
        widget.destroy()

    table_frame = ctk.CTkFrame(result_frame, corner_radius=0, border_width=1, border_color=border_color)
    table_frame.pack(padx=10, pady=10)

    full_table = [headers] + rows

    for row_idx, row in enumerate(full_table):
        for col_idx, value in enumerate(row):
            is_col_header = row_idx == 0
            is_row_header = col_idx == 0
            is_header = is_col_header or is_row_header
            is_note_cell = (row_idx == 1 and col_idx == len(row) - 1 and value == "※ 첫 튜닝시에 적용")

            text_color = "#cc0000" if is_note_cell else "black"
            fg_color = header_bg if is_header else cell_bg
            font = ("Segoe UI", 11, "bold", "italic") if is_note_cell else (header_font if is_header else cell_font)

            if not is_header and not is_note_cell:
                try:
                    if float(value) != 0:
                        fg_color = "#fffacd"
                        text_color = "#000080"
                        font = ("Segoe UI", 14, "bold")
                except ValueError:
                    pass

            label = ctk.CTkLabel(
                table_frame,
                text=str(value),
                width=200 if col_idx == len(row) - 1 else 60,
                height=35,
                fg_color=fg_color,
                text_color=text_color,
                font=font,
                corner_radius=0,
                anchor="w" if (col_idx == len(row) - 1 and row_idx != 0) else "center"
            )
            label.grid(row=row_idx, column=col_idx, padx=(0 if col_idx == 0 else 1), pady=(0 if row_idx == 0 else 1), sticky="nsew")
            result_table_labels.append(label)

    zone_data_global = extract_all_zones_all_series_limited(data_rows, recipe_step)
    root.after(100, lambda: create_zone_header_buttons(table_frame, headers))

# --- GUI 구성 ---

control_frame = ctk.CTkFrame(root, fg_color="transparent")
control_frame.pack(anchor='w', padx=20, pady=10)

ctk.CTkLabel(control_frame, text="①", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky='e', padx=5, pady=5)
upload_button = ctk.CTkButton(control_frame, text="CSV 업로드", command=upload_and_process)
upload_button.grid(row=0, column=1, sticky='w', pady=5)

file_path_label = ctk.CTkLabel(control_frame, text="선택된 파일 없음", width=800, anchor='w', text_color="#cc0000", font=("Segoe UI", 13, "bold", "italic"))
file_path_label.grid(row=1, column=1, columnspan=2, sticky='w', pady=2)

ctk.CTkLabel(control_frame, text="②", font=("Segoe UI", 13, "bold")).grid(row=2, column=0, sticky='e', padx=5, pady=5)
temp_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
temp_frame.grid(row=2, column=1, sticky='w', pady=2)
ctk.CTkLabel(temp_frame, text="Temp Control Mode 선택").pack(side='left', padx=(0, 5))
temp_cmode_menu = ctk.CTkComboBox(temp_frame, variable=selected_temp_cmode, values=['normal', 'high'])
temp_cmode_menu.pack(side='left')

ctk.CTkLabel(control_frame, text="③", font=("Segoe UI", 13, "bold")).grid(row=3, column=0, sticky='e', padx=5, pady=5)
etype_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
etype_frame.grid(row=3, column=1, sticky='w', pady=2)
ctk.CTkLabel(etype_frame, text="설비군 선택").pack(side='left', padx=(0, 5))
etype_menu = ctk.CTkComboBox(etype_frame, variable=selected_etype, values=['BCl3', 'Annealing', 'POCl3', 'Oxidation'])
etype_menu.pack(side='left')

ctk.CTkLabel(control_frame, text="④", font=("Segoe UI", 13, "bold")).grid(row=4, column=0, sticky='e', padx=5, pady=10)
run_button = ctk.CTkButton(control_frame, text="분석 실행", command=run_analysis)
run_button.grid(row=4, column=1, sticky='w', pady=10)

result_label = ctk.CTkLabel(root, text="", anchor='w')
result_label.pack(anchor='w', padx=20)

result_frame = ctk.CTkFrame(root, fg_color="transparent")
result_frame.pack(pady=10, anchor='w', padx=20)

graph_frame = ctk.CTkFrame(root, fg_color="transparent")
graph_frame.pack(anchor='w', padx=20, pady=10)

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

root.mainloop()