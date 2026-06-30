#!/usr/bin/env python3
"""
Gauss Gun Analyzer - Edition Scientifique (Graphiques & Stats Multi-Séries)
Dépendances requises : pip install pyserial matplotlib numpy
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import tkinter.font as tkfont
import serial
import serial.tools.list_ports
import threading
import queue
import re
import os
from datetime import datetime
import warnings

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ─── Palette de couleurs ─────────────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#21262d"
BORDER    = "#30363d"
ACCENT    = "#00d4aa"
ACCENT2   = "#005f4e"
TEXT      = "#e6edf3"
TEXT_DIM  = "#8b949e"
ERROR     = "#f85149"
SUCCESS   = "#3fb950"

# Dictionnaire de couleurs lisibles avec puces pour la liste déroulante
COLORS_DICT = {
    "🔴 Rouge": "#f85149",
    "🔵 Bleu": "#58a6ff",
    "🟢 Vert": "#3fb950",
    "🟣 Violet": "#d2a8ff",
    "🟡 Jaune": "#e3b341",
    "💠 Cyan": "#00d4aa",
    "🟠 Orange": "#ff7b72",
    "💎 Bleu Clair": "#79c0ff"
}

class GaussGunMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gauss Gun Analyzer")
        self.configure(bg=BG)
        self.geometry("1400x900")

        # Variables générales
        self._serial = None
        self._running = False
        self._queue = queue.Queue()
        
        # Initialisation des polices dynamiques
        self.base_size = 9
        self.font_mono = tkfont.Font(family="Courier New", size=self.base_size + 2)
        self.font_ui = tkfont.Font(family="Courier New", size=self.base_size, weight="bold")
        self.font_small = tkfont.Font(family="Courier New", size=self.base_size)
        self.font_icon = tkfont.Font(family="Arial", size=self.base_size + 6)
        
        # Données du mode Enregistrement
        self._history = []       
        self._raw_history = []   
        self._last_data = {'S':["--"]*4, 'E':["--"]*4, 'L': ["--"]*4, 'V':["--"]*4, 'Vinter': ["--"]*3}
        self._var_active_c = []  # Cases à cocher pour ignorer des capteurs

        # Données du mode Analyse
        self.analysis_datasets = [] # Liste de dicts
        self.ds_counter = 1

        self._apply_ttk_style()
        self._build_ui()
        self._refresh_ports()
        self._poll_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_ttk_style(self):
        s = ttk.Style(self)
        s.theme_use("alt")
        # Style Combobox
        s.configure("TCombobox", fieldbackground=BG2, background=BG3, foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER, padding=3)
        s.map("TCombobox", fieldbackground=[("readonly", BG2)], foreground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", BG2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        # Style Notebook
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=TEXT_DIM, padding=[15, 5], font=self.font_ui)
        s.map("TNotebook.Tab", background=[("selected", ACCENT2)], foreground=[("selected", TEXT)])

    # =========================================================================
    # GESTION DE LA TAILLE DU TEXTE
    # =========================================================================
    def _increase_font(self):
        if self.base_size < 18:
            self.base_size += 1
            self._update_fonts()

    def _decrease_font(self):
        if self.base_size > 6:
            self.base_size -= 1
            self._update_fonts()

    def _update_fonts(self):
        self.font_mono.configure(size=self.base_size + 2)
        self.font_ui.configure(size=self.base_size)
        self.font_small.configure(size=self.base_size)
        self.font_icon.configure(size=self.base_size + 6)
        
        s = ttk.Style()
        s.configure("TNotebook.Tab", font=self.font_ui)
        
        self._update_displays()
        self._update_analysis_displays()

    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, height=40)
        topbar.pack(fill="x", side="top")
        
        tk.Label(topbar, text=" GAUSS GUN ANALYZER", bg=BG2, fg=ACCENT, font=("Courier New", 14, "bold")).pack(side="left", padx=15)
        
        font_ctrl = tk.Frame(topbar, bg=BG2)
        font_ctrl.pack(side="right", padx=15, pady=5)
        tk.Label(font_ctrl, text="Taille Texte :", bg=BG2, fg=TEXT_DIM, font=self.font_small).pack(side="left", padx=5)
        tk.Button(font_ctrl, text="- A", command=self._decrease_font, bg=BG3, fg=TEXT, relief="flat", font=self.font_small).pack(side="left", padx=2)
        tk.Button(font_ctrl, text="+ A", command=self._increase_font, bg=BG3, fg=TEXT, relief="flat", font=self.font_small).pack(side="left", padx=2)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_record = tk.Frame(self.notebook, bg=BG)
        self.tab_analyze = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_record, text="🔴 ENREGISTREMENT")
        self.notebook.add(self.tab_analyze, text="📊 ANALYSE DE RÉSULTATS")

        self._build_tab_record()
        self._build_tab_analyze()

    # =========================================================================
    # TAB 1 : ENREGISTREMENT (Direct)
    # =========================================================================
    def _build_tab_record(self):
        container = self.tab_record
        container.columnconfigure((0,1), weight=1)
        container.rowconfigure(1, weight=1) 
        container.rowconfigure(2, weight=1) 

        # ─── PARAMÈTRES ───
        config_frame = tk.Frame(container, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        config_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=8)
        tk.Label(config_frame, text="PARAMÈTRES DU TIR", bg=BG3, fg=ACCENT, font=self.font_ui).pack(pady=10)
        
        f1 = tk.Frame(config_frame, bg=BG3)
        f1.pack(fill="x", padx=20, pady=5)
        tk.Label(f1, text="Longueur Chariot L (mm):", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        self._var_l_chariot = tk.StringVar(value="20.0")
        tk.Entry(f1, textvariable=self._var_l_chariot, bg=BG2, fg=TEXT, width=10, relief="flat", font=self.font_small, insertbackground=TEXT).pack(side="right")

        f2 = tk.Frame(config_frame, bg=BG3)
        f2.pack(fill="x", padx=20, pady=5)
        tk.Label(f2, text="Espacement Capteurs D (mm):", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        self._var_d_capteur = tk.StringVar(value="45.0")
        tk.Entry(f2, textvariable=self._var_d_capteur, bg=BG2, fg=TEXT, width=10, relief="flat", font=self.font_small, insertbackground=TEXT).pack(side="right")

        f3 = tk.Frame(config_frame, bg=BG3)
        f3.pack(fill="x", padx=20, pady=5)
        tk.Label(f3, text="Unité temporelle:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        self._var_time_unit = tk.StringVar(value="ms")
        cb_time = ttk.Combobox(f3, textvariable=self._var_time_unit, values=["ns", "µs", "ms"], width=5, state="readonly", font=self.font_small)
        cb_time.pack(side="right")
        cb_time.bind("<<ComboboxSelected>>", self._update_displays)

        f4 = tk.Frame(config_frame, bg=BG3)
        f4.pack(fill="x", padx=20, pady=5)
        tk.Label(f4, text="Décimales affichées:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        self._var_decimals = tk.StringVar(value="2")
        cb_dec = ttk.Combobox(f4, textvariable=self._var_decimals, values=["0", "1", "2", "3", "4"], width=5, state="readonly", font=self.font_small)
        cb_dec.pack(side="right")
        cb_dec.bind("<<ComboboxSelected>>", self._update_displays)
        
        # Sélection des capteurs actifs
        self._var_active_c = [tk.BooleanVar(value=True) for _ in range(4)]
        f5 = tk.Frame(config_frame, bg=BG3)
        f5.pack(fill="x", padx=20, pady=5)
        tk.Label(f5, text="Capteurs Actifs:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        for i in range(4):
            tk.Checkbutton(f5, text=f"C{i}", variable=self._var_active_c[i], command=self._update_displays,
                           bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3, font=self.font_small).pack(side="left", padx=2)

        # ─── MONITEUR & LOGS ───
        serial_area = tk.Frame(container, bg=BG2, highlightbackground=ACCENT2, highlightthickness=1)
        serial_area.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=8)
        
        s_ctrl = tk.Frame(serial_area, bg=BG3)
        s_ctrl.pack(fill="x")
        self._port_var = tk.StringVar()
        self._port_cb = ttk.Combobox(s_ctrl, textvariable=self._port_var, width=12, state="readonly", font=self.font_small)
        self._port_cb.pack(side="left", padx=5, pady=5)
        self._baud_var = tk.StringVar(value="115200")
        ttk.Combobox(s_ctrl, textvariable=self._baud_var, values=["9600", "115200"], width=8, state="readonly", font=self.font_small).pack(side="left", padx=5)
        self._btn_connect = tk.Button(s_ctrl, text="CONNECTER", command=self._toggle_connection, bg=ACCENT, fg=BG, relief="flat", font=self.font_small)
        self._btn_connect.pack(side="left", padx=5)

        self._txt = scrolledtext.ScrolledText(serial_area, bg=BG, fg=TEXT, font=self.font_mono, height=10, borderwidth=0)
        self._txt.pack(fill="both", expand=True)

        log_bar = tk.Frame(serial_area, bg=BG3)
        log_bar.pack(fill="x")
        self._lbl_log_status = tk.Label(log_bar, text="Données en mémoire: 0", bg=BG3, fg=TEXT_DIM, font=self.font_small)
        self._lbl_log_status.pack(side="left", padx=10)
        
        tk.Button(log_bar, text="🗑️ SUPPRIMER", command=self._delete_shot, bg=BG2, fg=TEXT_DIM, relief="flat", font=self.font_ui).pack(side="right", padx=2, pady=2)
        tk.Button(log_bar, text="🧹 VIDER", command=self._clear_memory, bg=BG2, fg=ERROR, relief="flat", font=self.font_ui).pack(side="right", padx=2, pady=2)
        tk.Button(log_bar, text="💾 EXPORT", command=self._export_data, bg=ACCENT2, fg=TEXT, relief="flat", font=self.font_ui).pack(side="right", padx=2, pady=2)
        tk.Button(log_bar, text="📂 IMPORT", command=self._import_data, bg=BG2, fg=ACCENT, relief="flat", font=self.font_ui).pack(side="right", padx=2, pady=2)

        # ─── SCHÉMA & CONTROLEUR ───
        schema_frame = tk.Frame(container, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        schema_frame.grid(row=2, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        
        self.schema_ctrl = tk.Frame(schema_frame, bg=BG3, height=30)
        self.schema_ctrl.pack(fill="x", side="top")
        
        tk.Label(self.schema_ctrl, text="Tir affiché:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left", padx=10)
        self._var_spin = tk.StringVar(value="1")
        self._spin_shot = ttk.Spinbox(self.schema_ctrl, from_=1, to=1, textvariable=self._var_spin, width=5, command=self._update_displays, font=self.font_small)
        self._spin_shot.pack(side="left")
        self._spin_shot.bind('<Return>', lambda e: self._update_displays())
        
        self._btn_last_shot = tk.Button(self.schema_ctrl, text="DERNIER", command=self._goto_last_shot, bg=BG2, fg=ACCENT, relief="flat", font=self.font_ui)
        self._btn_last_shot.pack(side="left", padx=10)
        
        self.canvas = tk.Canvas(schema_frame, bg=BG2, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_schema())

        # ─── GRAPHIQUE ───
        graph_frame = tk.Frame(container, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        graph_frame.grid(row=2, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        
        graph_ctrl = tk.Frame(graph_frame, bg=BG3, height=30)
        graph_ctrl.pack(fill="x", side="top")
        
        self._show_avg_var = tk.BooleanVar(value=False)
        tk.Checkbutton(graph_ctrl, text="Moyenne", variable=self._show_avg_var, 
                       command=self._update_displays, bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3, font=self.font_small).pack(side="left", padx=(5, 5))

        self._show_labels_var = tk.BooleanVar(value=False)
        tk.Checkbutton(graph_ctrl, text="Valeurs", variable=self._show_labels_var, 
                       command=self._update_displays, bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3, font=self.font_small).pack(side="left", padx=(0, 5))
        
        tk.Label(graph_ctrl, text="X Capteurs:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left", padx=(5, 2))
        self._var_x_ref = tk.StringVar(value="Milieu (L/2)")
        cb_x_ref = ttk.Combobox(graph_ctrl, textvariable=self._var_x_ref, values=["Milieu (L/2)", "Fin (L)", "Capteur (0)"], width=10, state="readonly", font=self.font_small)
        cb_x_ref.pack(side="left")
        cb_x_ref.bind("<<ComboboxSelected>>", self._update_displays)

        tk.Label(graph_ctrl, text="X Inter-bobines:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left", padx=(5, 2))
        self._var_x_vinter = tk.StringVar(value="Milieu") 
        cb_x_vinter = ttk.Combobox(graph_ctrl, textvariable=self._var_x_vinter, values=["Caché", "Début", "Milieu", "Fin"], width=7, state="readonly", font=self.font_small)
        cb_x_vinter.pack(side="left")
        cb_x_vinter.bind("<<ComboboxSelected>>", self._update_displays)

        tk.Label(graph_ctrl, text="V0:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left", padx=(5, 2))
        self._var_v0 = tk.StringVar(value="0 m/s")
        cb_v0 = ttk.Combobox(graph_ctrl, textvariable=self._var_v0, values=["Indéfini", "0 m/s"], width=8, state="readonly", font=self.font_small)
        cb_v0.pack(side="left")
        cb_v0.bind("<<ComboboxSelected>>", self._update_displays)

        self.fig, self.ax = plt.subplots(figsize=(5, 3), facecolor=BG2)
        self.fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.2)
        self.ax.set_facecolor(BG)
        self.ax.tick_params(colors=TEXT_DIM)
        for spine in self.ax.spines.values(): spine.set_color(BORDER)
        self.ax.yaxis.label.set_color(TEXT_DIM)
        self.ax.xaxis.label.set_color(TEXT_DIM)
        
        self.canvas_graph = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas_graph.get_tk_widget().pack(fill="both", expand=True)

    # =========================================================================
    # TAB 2 : ANALYSE (Multi-Séries)
    # =========================================================================
    def _build_tab_analyze(self):
        container = self.tab_analyze
        container.columnconfigure((0,1), weight=1)
        container.rowconfigure(0, weight=1) 
        container.rowconfigure(1, weight=3) 

        # ─── HAUT GAUCHE : LISTE DES SÉRIES ───
        list_frame = tk.Frame(container, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=(8, 4))
        
        list_top = tk.Frame(list_frame, bg=BG3, height=30)
        list_top.pack(fill="x", side="top")
        tk.Label(list_top, text="SÉRIES IMPORTÉES", bg=BG3, fg=ACCENT, font=self.font_ui).pack(side="left", padx=10)
        tk.Button(list_top, text="⚙️ CONFIG GLOBALE", command=self._show_ana_global_config, bg=BG2, fg=TEXT, relief="flat", font=self.font_ui).pack(side="right", padx=5, pady=2)
        tk.Button(list_top, text="📂 IMPORTER LISTE", command=self._import_analysis_ds, bg=ACCENT2, fg=TEXT, relief="flat", font=self.font_ui).pack(side="right", padx=5, pady=2)

        self.ana_list_canvas = tk.Canvas(list_frame, bg=BG2, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.ana_list_canvas.yview)
        self.ana_list_inner = tk.Frame(self.ana_list_canvas, bg=BG2)
        
        self.ana_list_inner.bind("<Configure>", lambda e: self.ana_list_canvas.configure(scrollregion=self.ana_list_canvas.bbox("all")))
        self.ana_list_canvas.create_window((0, 0), window=self.ana_list_inner, anchor="nw", width=550)
        self.ana_list_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.ana_list_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # ─── HAUT DROIT : PANNEAU CONFIGURATION ───
        self.ana_config_frame = tk.Frame(container, bg=BG3, highlightbackground=BORDER, highlightthickness=1)
        self.ana_config_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=(8, 4))
        
        self._var_ana_title = tk.StringVar(value="Comparaison des vitesses inter-bobines")
        self._var_ana_time_unit = tk.StringVar(value="ms")
        self._var_ana_dec = tk.StringVar(value="2")
        self._var_ana_x_ref = tk.StringVar(value="Milieu (L/2)")
        self._var_ana_vinter = tk.StringVar(value="Milieu")
        self._var_ana_v0 = tk.StringVar(value="0 m/s")
        self._var_ana_show_values = tk.BooleanVar(value=False)
        
        self._show_ana_global_config()

        # ─── BAS GAUCHE : SCHÉMA REGROUPÉ ───
        schema_frame = tk.Frame(container, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        schema_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(4, 8))
        self.ana_canvas_schema = tk.Canvas(schema_frame, bg=BG2, highlightthickness=0)
        self.ana_canvas_schema.pack(fill="both", expand=True)
        self.ana_canvas_schema.bind("<Configure>", lambda e: self._draw_analysis_schema())

        # ─── BAS DROIT : GRAPHIQUE MULTI-SÉRIES ───
        graph_frame = tk.Frame(container, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        graph_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(4, 8))
        
        self.ana_fig, self.ana_ax = plt.subplots(figsize=(5, 3), facecolor=BG2)
        self.ana_fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.2)
        self.ana_ax.set_facecolor(BG)
        self.ana_ax.tick_params(colors=TEXT_DIM)
        for spine in self.ana_ax.spines.values(): spine.set_color(BORDER)
        self.ana_ax.yaxis.label.set_color(TEXT_DIM)
        self.ana_ax.xaxis.label.set_color(TEXT_DIM)
        
        self.ana_canvas_graph = FigureCanvasTkAgg(self.ana_fig, master=graph_frame)
        self.ana_canvas_graph.get_tk_widget().pack(fill="both", expand=True)


    # =========================================================================
    # LOGIQUE ONGLET 2 (ANALYSE)
    # =========================================================================
    
    def _render_ds_list(self):
        for widget in self.ana_list_inner.winfo_children():
            widget.destroy()
            
        for i, ds in enumerate(self.analysis_datasets):
            row = tk.Frame(self.ana_list_inner, bg=BG3, pady=5)
            row.pack(fill="x", pady=2, padx=2)
            
            f_arr = tk.Frame(row, bg=BG3)
            f_arr.pack(side="left", padx=5)
            tk.Button(f_arr, text="▲", command=lambda idx=i: self._move_ds(idx, -1), bg=BG, fg=TEXT_DIM, font=("Courier", 6), relief="flat", pady=0).pack(side="top")
            tk.Button(f_arr, text="▼", command=lambda idx=i: self._move_ds(idx, 1), bg=BG, fg=TEXT_DIM, font=("Courier", 6), relief="flat", pady=0).pack(side="top")
            
            # Utilisation de la couleur stockée pour l'indicateur
            tk.Label(row, text="■", fg=ds['color'], bg=BG3, font=self.font_icon).pack(side="left", padx=5)
            
            tk.Label(row, text=f"{ds['id']}. {ds['name']} (n={len(ds['raw_data'])})", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left", padx=5)
            
            tk.Button(row, text="❌", command=lambda idx=i: self._delete_ds(idx), bg=BG3, fg=ERROR, relief="flat", font=self.font_small).pack(side="right", padx=5)
            tk.Button(row, text="⚙️ CONFIG", command=lambda d=ds: self._show_ds_config(d), bg=BG2, fg=ACCENT, relief="flat", font=self.font_small).pack(side="right", padx=5)

    def _move_ds(self, idx, direction):
        new_idx = idx + direction
        if 0 <= new_idx < len(self.analysis_datasets):
            self.analysis_datasets[idx], self.analysis_datasets[new_idx] = self.analysis_datasets[new_idx], self.analysis_datasets[idx]
            self._render_ds_list()
            self._update_analysis_displays()

    def _delete_ds(self, idx):
        self.analysis_datasets.pop(idx)
        self._render_ds_list()
        self._update_analysis_displays()
        self._show_ana_global_config()

    def _import_analysis_ds(self):
        file_path = filedialog.askopenfilename(filetypes=[("Fichier CSV", "*.csv")])
        if not file_path: return
        
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
                
            raw_data = []
            for line in lines:
                if "OFFSET" in line.upper() or not line.strip(): continue
                parts = line.strip().split(';')
                if len(parts) >= 13:
                    try: raw_data.append([float(p.replace(',', '.')) for p in parts[:13]])
                    except ValueError: pass
            
            if not raw_data: return 
                
            base_name = os.path.basename(file_path).replace('.csv', '')
            name = base_name
            existing_names = [d['name'] for d in self.analysis_datasets]
            count = 1
            while name in existing_names:
                name = f"{base_name} ({count})"
                count += 1
                
            color_names = list(COLORS_DICT.keys())
            c_name = color_names[len(self.analysis_datasets) % len(color_names)]
            c_hex = COLORS_DICT[c_name]
            
            try: L_def = float(self._var_l_chariot.get())
            except: L_def = 20.0
            try: D_def = float(self._var_d_capteur.get())
            except: D_def = 45.0
            
            ds = {
                'id': self.ds_counter,
                'name': name,
                'color_name': c_name,
                'color': c_hex,
                'raw_data': raw_data,
                'L': L_def,
                'D': D_def,
                'active': [True, True, True, True] # Capteurs actifs par défaut
            }
            self.analysis_datasets.append(ds)
            self.ds_counter += 1
            
            self._render_ds_list()
            self._update_analysis_displays()
            
        except Exception as e:
            print("Erreur import analyse:", e)

    def _clear_ana_config(self):
        for widget in self.ana_config_frame.winfo_children():
            widget.destroy()

    def _show_ana_global_config(self):
        self._clear_ana_config()
        tk.Label(self.ana_config_frame, text="⚙️ CONFIGURATION GLOBALE", bg=BG3, fg=ACCENT, font=self.font_ui).pack(pady=10)
        
        f1 = tk.Frame(self.ana_config_frame, bg=BG3)
        f1.pack(fill="x", padx=20, pady=5)
        tk.Label(f1, text="Titre Graphique:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        en = tk.Entry(f1, textvariable=self._var_ana_title, bg=BG2, fg=TEXT, relief="flat", font=self.font_small, insertbackground=TEXT)
        en.pack(side="right", fill="x", expand=True, padx=(10,0))
        en.bind("<KeyRelease>", lambda e: self._update_analysis_displays())
        
        f2 = tk.Frame(self.ana_config_frame, bg=BG3)
        f2.pack(fill="x", padx=20, pady=5)
        tk.Label(f2, text="Unité temporelle:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        cb_u = ttk.Combobox(f2, textvariable=self._var_ana_time_unit, values=["ns", "µs", "ms"], width=5, state="readonly", font=self.font_small)
        cb_u.pack(side="right")
        cb_u.bind("<<ComboboxSelected>>", lambda e: self._update_analysis_displays())
        
        f3 = tk.Frame(self.ana_config_frame, bg=BG3)
        f3.pack(fill="x", padx=20, pady=5)
        tk.Label(f3, text="Décimales affichées:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        cb_d = ttk.Combobox(f3, textvariable=self._var_ana_dec, values=["0", "1", "2", "3", "4"], width=5, state="readonly", font=self.font_small)
        cb_d.pack(side="right")
        cb_d.bind("<<ComboboxSelected>>", lambda e: self._update_analysis_displays())

        f4 = tk.Frame(self.ana_config_frame, bg=BG3)
        f4.pack(fill="x", padx=20, pady=5)
        tk.Label(f4, text="V0 Initiale:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        cb_v0 = ttk.Combobox(f4, textvariable=self._var_ana_v0, values=["Indéfini", "0 m/s"], width=8, state="readonly", font=self.font_small)
        cb_v0.pack(side="right")
        cb_v0.bind("<<ComboboxSelected>>", lambda e: self._update_analysis_displays())

        f5 = tk.Frame(self.ana_config_frame, bg=BG3)
        f5.pack(fill="x", padx=20, pady=5)
        tk.Label(f5, text="Position X Capteurs:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        cb_x = ttk.Combobox(f5, textvariable=self._var_ana_x_ref, values=["Milieu (L/2)", "Fin (L)", "Capteur (0)"], width=12, state="readonly", font=self.font_small)
        cb_x.pack(side="right")
        cb_x.bind("<<ComboboxSelected>>", lambda e: self._update_analysis_displays())

        f6 = tk.Frame(self.ana_config_frame, bg=BG3)
        f6.pack(fill="x", padx=20, pady=5)
        tk.Label(f6, text="Position X V.Inter:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        cb_xi = ttk.Combobox(f6, textvariable=self._var_ana_vinter, values=["Caché", "Début", "Milieu", "Fin"], width=12, state="readonly", font=self.font_small)
        cb_xi.pack(side="right")
        cb_xi.bind("<<ComboboxSelected>>", lambda e: self._update_analysis_displays())

        f7 = tk.Frame(self.ana_config_frame, bg=BG3)
        f7.pack(fill="x", padx=20, pady=15)
        tk.Checkbutton(f7, text="Afficher les étiquettes de données sur les courbes", 
                       variable=self._var_ana_show_values,
                       command=self._update_analysis_displays,
                       bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3, 
                       font=self.font_small).pack(side="left")

    def _show_ds_config(self, ds):
        self._clear_ana_config()
        tk.Label(self.ana_config_frame, text=f"⚙️ SÉRIE : {ds['name']}", bg=BG3, fg=ACCENT, font=self.font_ui).pack(pady=10)
        
        v_l = tk.StringVar(value=str(ds['L']))
        v_d = tk.StringVar(value=str(ds['D']))
        v_c = tk.StringVar(value=ds.get('color_name', list(COLORS_DICT.keys())[0]))
        
        f1 = tk.Frame(self.ana_config_frame, bg=BG3)
        f1.pack(fill="x", padx=20, pady=5)
        tk.Label(f1, text="L Chariot (mm):", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        tk.Entry(f1, textvariable=v_l, bg=BG2, fg=TEXT, width=8, relief="flat", font=self.font_small, insertbackground=TEXT).pack(side="right")
        
        f2 = tk.Frame(self.ana_config_frame, bg=BG3)
        f2.pack(fill="x", padx=20, pady=5)
        tk.Label(f2, text="D Capteurs (mm):", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        tk.Entry(f2, textvariable=v_d, bg=BG2, fg=TEXT, width=8, relief="flat", font=self.font_small, insertbackground=TEXT).pack(side="right")
        
        f3 = tk.Frame(self.ana_config_frame, bg=BG3)
        f3.pack(fill="x", padx=20, pady=5)
        tk.Label(f3, text="Couleur :", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        
        lbl_color_preview = tk.Label(f3, text="■", bg=BG3, font=self.font_icon)
        lbl_color_preview.pack(side="right", padx=(5, 0))
        
        cb_col = ttk.Combobox(f3, textvariable=v_c, values=list(COLORS_DICT.keys()), width=14, font=self.font_small, state="readonly")
        cb_col.pack(side="right")
        
        def update_preview(*args):
            hex_color = COLORS_DICT.get(v_c.get(), "#ffffff")
            lbl_color_preview.config(fg=hex_color)

        update_preview()
        cb_col.bind("<<ComboboxSelected>>", update_preview)
        
        # Sélection capteurs actifs pour CETTE série
        f4 = tk.Frame(self.ana_config_frame, bg=BG3)
        f4.pack(fill="x", padx=20, pady=15)
        tk.Label(f4, text="Capteurs Actifs:", bg=BG3, fg=TEXT, font=self.font_small).pack(side="left")
        vars_active = [tk.BooleanVar(value=ds['active'][i]) for i in range(4)]
        for i in range(4):
            tk.Checkbutton(f4, text=f"C{i}", variable=vars_active[i], bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3, font=self.font_small).pack(side="left", padx=2)
        
        def save_ds():
            try:
                ds['L'] = float(v_l.get())
                ds['D'] = float(v_d.get())
                ds['color_name'] = v_c.get()
                ds['color'] = COLORS_DICT.get(v_c.get(), "#ffffff")
                ds['active'] = [v.get() for v in vars_active]
                self._render_ds_list()
                self._update_analysis_displays()
                self._show_ana_global_config() 
            except: pass

        tk.Button(self.ana_config_frame, text="SAUVEGARDER & RETOUR", command=save_ds, bg=ACCENT2, fg=TEXT, relief="flat", font=self.font_ui).pack(pady=20)

    def _update_analysis_displays(self, event=None):
        self._update_analysis_graph()
        self._draw_analysis_schema()

    def _draw_analysis_schema(self):
        self.ana_canvas_schema.delete("all")
        w, h = self.ana_canvas_schema.winfo_width(), self.ana_canvas_schema.winfo_height()
        if w < 100: return
        
        margin = 60
        step = (w - 2 * margin) / 3
        
        mid_y = max(80 + (self.base_size * 2), h // 3)
        self.ana_canvas_schema.create_line(margin-30, mid_y, w-margin+30, mid_y, fill=BORDER, width=2)
        
        time_unit = self._var_ana_time_unit.get()
        if time_unit == "ns": tf = 1.0
        elif time_unit == "µs": tf = 1000.0
        else: tf = 1000000.0
        
        fmt = f".{self._var_ana_dec.get()}f"

        for i in range(4):
            x = margin + i * step
            self.ana_canvas_schema.create_rectangle(x-20, mid_y-20, x+20, mid_y+20, fill=ACCENT2, outline=ACCENT)
            self.ana_canvas_schema.create_text(x, mid_y, text=f"C{i}", fill=TEXT, font=self.font_ui)
            
            if i < 3:
                self.ana_canvas_schema.create_line(x+25, mid_y-15, x+step-25, mid_y-15, arrow=tk.LAST, fill=ACCENT2)

            curr_y = mid_y + 35
            
            lines_S, lines_E, lines_L, lines_V, lines_Vint = [], [], [], [], []
            
            for ds in self.analysis_datasets:
                c = ds['color']
                L_char = ds['L']
                D_capt = ds['D']
                mult = 1000000
                
                # Ignorer l'extraction si le capteur est désactivé pour cette série
                if ds['active'][i]:
                    S_vals = [r[1+i*3] for r in ds['raw_data'] if len(r)>1+i*3]
                    E_vals = [r[2+i*3] for r in ds['raw_data'] if len(r)>2+i*3]
                    L_vals = [r[3+i*3] for r in ds['raw_data'] if len(r)>3+i*3 and r[3+i*3]>0]
                    V_vals = [(L_char/l)*mult for l in L_vals]
                else:
                    S_vals, E_vals, L_vals, V_vals = [], [], [], []
                
                mS = np.mean(S_vals) if S_vals else np.nan
                uS = self._calc_expanded_uncertainty(S_vals)
                mE = np.mean(E_vals) if E_vals else np.nan
                uE = self._calc_expanded_uncertainty(E_vals)
                mL = np.mean(L_vals) if L_vals else np.nan
                uL = self._calc_expanded_uncertainty(L_vals)
                mV = np.mean(V_vals) if V_vals else np.nan
                uV = self._calc_expanded_uncertainty(V_vals)
                
                s_str = f"{format(mS/tf, fmt)}\u00B1{format(uS/tf, fmt)}" if not np.isnan(mS) else "--"
                lines_S.append((s_str, c))
                e_str = f"{format(mE/tf, fmt)}\u00B1{format(uE/tf, fmt)}" if not np.isnan(mE) else "--"
                lines_E.append((e_str, c))
                l_str = f"{format(mL/tf, fmt)}\u00B1{format(uL/tf, fmt)}" if not np.isnan(mL) else "--"
                lines_L.append((l_str, c))
                v_str = f"{format(mV, fmt)}\u00B1{format(uV, fmt)}" if not np.isnan(mV) else "--"
                lines_V.append((v_str, c))
                
                if i < 3:
                    vint_vals = []
                    # Vinter est valide uniquement si les 2 capteurs contigus sont actifs
                    if ds['active'][i] and ds['active'][i+1]:
                        for r in ds['raw_data']:
                            if len(r)>4+i*3:
                                dt = r[4+i*3] - r[2+i*3] 
                                if dt > 0: vint_vals.append(((D_capt - L_char)/dt)*mult)
                    mVi = np.mean(vint_vals) if vint_vals else np.nan
                    uVi = self._calc_expanded_uncertainty(vint_vals)
                    vi_str = f"{format(mVi, fmt)}\u00B1{format(uVi, fmt)}" if not np.isnan(mVi) else "--"
                    lines_Vint.append((vi_str, c))

            lh = self.base_size + 6 
            
            self.ana_canvas_schema.create_text(x-35, curr_y, text="S\u0304:", fill=TEXT_DIM, font=self.font_small, anchor="e")
            for t, c in lines_S:
                self.ana_canvas_schema.create_text(x-30, curr_y, text=t, fill=c, font=self.font_small, anchor="w")
                curr_y += lh
            
            curr_y += 4
            self.ana_canvas_schema.create_text(x-35, curr_y, text="E\u0304:", fill=TEXT_DIM, font=self.font_small, anchor="e")
            for t, c in lines_E:
                self.ana_canvas_schema.create_text(x-30, curr_y, text=t, fill=c, font=self.font_small, anchor="w")
                curr_y += lh
                
            curr_y += 4
            self.ana_canvas_schema.create_text(x-35, curr_y, text="dT\u0304:", fill=TEXT_DIM, font=self.font_small, anchor="e")
            for t, c in lines_L:
                self.ana_canvas_schema.create_text(x-30, curr_y, text=t, fill=c, font=self.font_small, anchor="w")
                curr_y += lh
                
            curr_y += 4
            self.ana_canvas_schema.create_text(x-35, curr_y, text="V\u0304:", fill=TEXT_DIM, font=self.font_ui, anchor="e")
            for t, c in lines_V:
                self.ana_canvas_schema.create_text(x-30, curr_y, text=t, fill=c, font=self.font_ui, anchor="w")
                curr_y += lh

            if i < 3:
                xm = x + step/2
                v_y_start = mid_y - 20 - (len(lines_Vint) * lh)
                self.ana_canvas_schema.create_text(xm-35, v_y_start, text="➔V\u0304:", fill=TEXT_DIM, font=self.font_ui, anchor="e")
                for t, c in lines_Vint:
                    self.ana_canvas_schema.create_text(xm-30, v_y_start, text=t, fill=c, font=self.font_ui, anchor="w")
                    v_y_start += lh

    def _update_analysis_graph(self):
        self.ana_ax.clear()
        self.ana_ax.set_facecolor(BG)
        self.ana_ax.tick_params(colors=TEXT_DIM, labelsize=self.base_size)
        for spine in self.ana_ax.spines.values(): spine.set_color(BORDER)
        
        self.ana_ax.set_xlabel("Position (mm)", color=TEXT_DIM, fontsize=self.base_size+1)
        self.ana_ax.set_ylabel("Vitesse (m/s)", color=TEXT_DIM, fontsize=self.base_size+1)
        
        self.ana_ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x:g} mm"))
        self.ana_ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, pos: f"{y:g} m/s"))
        
        title = self._var_ana_title.get()
        if title: self.ana_ax.set_title(title, color=TEXT, fontsize=self.base_size+2)

        if not self.analysis_datasets:
            self.ana_canvas_graph.draw()
            return

        ref_x = self._var_ana_x_ref.get()
        ref_vi = self._var_ana_vinter.get()
        add_v0 = (self._var_ana_v0.get() == "0 m/s")
        show_labels = self._var_ana_show_values.get()
        dec = self._var_ana_dec.get()
        
        max_x = 0

        for ds in self.analysis_datasets:
            L = ds['L']
            D = ds['D']
            c = ds['color']
            n = len(ds['raw_data'])
            mult = 1000000
            
            if "Milieu" in ref_x: offset = L / 2.0  
            elif "Fin" in ref_x: offset = L        
            else: offset = 0.0
            
            X_main = [offset, offset + D, offset + 2*D, offset + 3*D]
            max_x = max(max_x, X_main[-1])
            
            V_matrix = []
            for r in ds['raw_data']:
                row = []
                for i in range(4):
                    if ds['active'][i] and len(r)>3+i*3 and r[3+i*3]>0: 
                        row.append((L/r[3+i*3])*mult)
                    else: 
                        row.append(np.nan)
                V_matrix.append(row)
            
            V_arr = np.array(V_matrix, dtype=float)
            Y_main, U_main = [], []
            if len(V_arr) > 0:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    Y_main = list(np.nanmean(V_arr, axis=0))
                if n > 1:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        stds = np.nanstd(V_arr, axis=0, ddof=1)
                    U_main = list(stds * self._get_student_t(n) / np.sqrt(n))
                else: U_main = [0.0]*4
                
            X_main_plot = list(X_main)
            if add_v0 and len(Y_main) > 0:
                X_main_plot = [0.0] + X_main_plot
                Y_main = [0.0] + Y_main
                U_main = [0.0] + U_main
            
            X_inter_plot = []
            Y_inter = []
            U_inter = []
            
            if ref_vi != "Caché":
                for i in range(3):
                    if "Début" in ref_vi: X_inter_plot.append(i*D + L)
                    elif "Fin" in ref_vi: X_inter_plot.append((i+1)*D)
                    else: X_inter_plot.append(i*D + (D+L)/2.0)
                
                Vi_matrix = []
                for r in ds['raw_data']:
                    row = []
                    for i in range(3):
                        if ds['active'][i] and ds['active'][i+1] and len(r)>4+i*3:
                            dt = r[4+i*3] - r[2+i*3]
                            if dt > 0: row.append(((D-L)/dt)*mult)
                            else: row.append(np.nan)
                        else: row.append(np.nan)
                    Vi_matrix.append(row)
                
                Vi_arr = np.array(Vi_matrix, dtype=float)
                if len(Vi_arr) > 0:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        Y_inter = list(np.nanmean(Vi_arr, axis=0))
                    if n > 1:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            stds_vi = np.nanstd(Vi_arr, axis=0, ddof=1)
                        U_inter = list(stds_vi * self._get_student_t(n) / np.sqrt(n))
                    else: U_inter = [0.0]*3
            
            X_all = list(X_main_plot) + list(X_inter_plot)
            Y_all = list(Y_main) + list(Y_inter)
            
            # zip and dropna naturally skip the disabled sensors bridging gaps perfectly!
            valid_pts = [(x, y) for x, y in zip(X_all, Y_all) if not np.isnan(y)]
            valid_pts.sort(key=lambda p: p[0])
            
            if valid_pts:
                X_line = [p[0] for p in valid_pts]
                Y_line = [p[1] for p in valid_pts]
                
                self.ana_ax.plot(X_line, Y_line, '-', color=c, alpha=0.5)
                
                self.ana_ax.errorbar(X_main_plot, Y_main, yerr=U_main, fmt='o', color=c, 
                                     capsize=4, elinewidth=1.5, markeredgewidth=1.5,
                                     label=f"{ds['name']} (n={n})")
                
                if X_inter_plot:
                    self.ana_ax.errorbar(X_inter_plot, Y_inter, yerr=U_inter, fmt='s', color=c, 
                                         markerfacecolor=BG2, capsize=3, markeredgewidth=1.5)

                if show_labels:
                    for x_val, y_val in zip(X_main_plot, Y_main):
                        if not np.isnan(y_val) and (x_val != 0.0 or add_v0):
                            self.ana_ax.annotate(f"{y_val:.{dec}f} m/s", (x_val, y_val),
                                                 textcoords="offset points", xytext=(0, 8), 
                                                 ha='center', va='bottom', fontsize=max(6, self.base_size - 1), color=c)
                    if X_inter_plot:
                        for x_val, y_val in zip(X_inter_plot, Y_inter):
                            if not np.isnan(y_val):
                                self.ana_ax.annotate(f"{y_val:.{dec}f} m/s", (x_val, y_val),
                                                     textcoords="offset points", xytext=(0, -8), 
                                                     ha='center', va='top', fontsize=max(6, self.base_size - 1), color=c)

        self.ana_ax.legend(loc="upper left", facecolor=BG3, edgecolor=BORDER, labelcolor=TEXT, fontsize=self.base_size)
        self.ana_ax.set_xlim(-10, max_x + 30)
        self.ana_ax.grid(True, linestyle='--', alpha=0.2, color=TEXT_DIM)
        
        self.ana_canvas_graph.draw()


    # =========================================================================
    # OUTILS ET GESTION ONGLET 1 (Enregistrement)
    # =========================================================================
    
    def _get_student_t(self, n):
        if n <= 1: return 0.0
        t_table = {
            2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 
            7: 2.45,  8: 2.36, 9: 2.31, 10: 2.26, 11: 2.23, 
            12: 2.20, 13: 2.18, 14: 2.16, 15: 2.14, 16: 2.13, 
            17: 2.12, 18: 2.11, 19: 2.10, 20: 2.09, 21: 2.08, 
            22: 2.07, 23: 2.07, 24: 2.06, 25: 2.06, 26: 2.06, 
            27: 2.05, 28: 2.05, 29: 2.05, 30: 2.04
        }
        return t_table.get(n, 1.96) 

    def _calc_expanded_uncertainty(self, vals):
        n = len(vals)
        if n > 1:
            t_val = self._get_student_t(n)
            return np.std(vals, ddof=1) * t_val / np.sqrt(n)
        return np.nan

    def _update_displays(self, event=None):
        n = len(self._history)
        if self._show_avg_var.get() or n == 0:
            self._spin_shot.config(state="disabled")
            self._btn_last_shot.config(state="disabled")
        else:
            self._spin_shot.config(state="normal", to=max(1, n))
            self._btn_last_shot.config(state="normal")
            
        self._update_graph()
        self._draw_schema()

    def _goto_last_shot(self):
        n = len(self._history)
        if n > 0:
            self._var_spin.set(str(n))
            self._update_displays()

    def _delete_shot(self):
        n = len(self._history)
        if n == 0: return

        if self._show_avg_var.get(): idx = n - 1 
        else:
            try:
                idx = int(self._var_spin.get()) - 1
                idx = max(0, min(idx, n - 1))
            except: idx = n - 1

        self._history.pop(idx)
        self._raw_history.pop(idx)
        
        new_n = len(self._history)
        self._append(f"Tir n°{idx+1} supprimé de la mémoire.\n", ERROR)
        self._lbl_log_status.config(text=f"Données en mémoire: {new_n}")
        
        if new_n == 0:
            self._var_spin.set("1")
            self._last_data = {'S': ["--"]*4, 'E': ["--"]*4, 'L': ["--"]*4, 'V': ["--"]*4, 'Vinter':["--"]*3}
        elif idx >= new_n:
            self._var_spin.set(str(new_n))
            
        self._update_displays()

    def _clear_memory(self):
        if self._history or self._raw_history:
            self._history.clear()
            self._raw_history.clear()
            self._var_spin.set("1")
            self._last_data = {'S': ["--"]*4, 'E': ["--"]*4, 'L': ["--"]*4, 'V': ["--"]*4, 'Vinter':["--"]*3}
            self._append("🧹 Mémoire entièrement vidée.\n", ERROR)
            self._lbl_log_status.config(text="Données en mémoire: 0", fg=TEXT_DIM)
            self._update_displays()

    def _update_graph(self):
        self.ax.clear()
        self.ax.set_facecolor(BG)
        self.ax.tick_params(colors=TEXT_DIM, labelsize=self.base_size)
        for spine in self.ax.spines.values(): spine.set_color(BORDER)
        self.ax.set_xlabel("Position (mm)", color=TEXT_DIM, fontsize=self.base_size+1)
        self.ax.set_ylabel("Vitesse (m/s)", color=TEXT_DIM, fontsize=self.base_size+1)

        self.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x:g} mm"))
        self.ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, pos: f"{y:g} m/s"))

        if not self._history:
            self.canvas_graph.draw()
            return

        try:
            D = float(self._var_d_capteur.get())
            L = float(self._var_l_chariot.get())
            dec = int(self._var_decimals.get())
            
            ref = self._var_x_ref.get()
            if "Milieu" in ref: offset = L / 2.0  
            elif "Fin" in ref: offset = L        
            else: offset = 0.0      
            X_main = [offset, offset + D, offset + 2*D, offset + 3*D]
            
            add_v0 = (self._var_v0.get() == "0 m/s")
            n_shots = len(self._history)
            
            try:
                idx = int(self._var_spin.get()) - 1
                idx = max(0, min(idx, n_shots - 1))
            except: idx = n_shots - 1
            
            hist_array = np.array(self._history, dtype=float)
            # Masquer les valeurs désactivées
            if len(hist_array) > 0:
                for i in range(4):
                    if not self._var_active_c[i].get():
                        hist_array[:, i] = np.nan

            Y_main_plot, U_main_plot = [], []
            
            if self._show_avg_var.get():
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    Y_main_plot = list(np.nanmean(hist_array, axis=0)) if len(hist_array) > 0 else []
                if n_shots > 1:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        stds = np.nanstd(hist_array, axis=0, ddof=1)
                    U_main_plot = list(stds * self._get_student_t(n_shots) / np.sqrt(n_shots))
                else: U_main_plot = [0.0] * 4
            else:
                Y_main_plot = list(hist_array[idx])
                U_main_plot = [0.0] * 4
                
            X_main_plot = list(X_main)
            if add_v0 and len(Y_main_plot) > 0:
                X_main_plot = [0.0] + X_main_plot
                Y_main_plot = [0.0] + Y_main_plot
                U_main_plot = [0.0] + U_main_plot

            vinter_pos = self._var_x_vinter.get()
            X_inter_plot = []
            Y_inter_plot = []
            U_inter_plot = []
            
            if vinter_pos != "Caché":
                for i in range(3):
                    if "Début" in vinter_pos: X_inter_plot.append(i*D + L)
                    elif "Fin" in vinter_pos: X_inter_plot.append((i+1)*D)
                    else: X_inter_plot.append(i*D + (D+L)/2.0) 
                
                vinter_matrix = []
                for raw in self._raw_history:
                    row = []
                    for i in range(3):
                        if self._var_active_c[i].get() and self._var_active_c[i+1].get() and len(raw) > 4+i*3:
                            dt = raw[4+i*3] - raw[2+i*3] 
                            if dt > 0: row.append(((D-L)/dt)*1000000)
                            else: row.append(np.nan)
                        else: row.append(np.nan)
                    vinter_matrix.append(row)
                
                if len(vinter_matrix) > 0:
                    vinter_array = np.array(vinter_matrix, dtype=float)
                    if self._show_avg_var.get():
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            Y_inter_plot = list(np.nanmean(vinter_array, axis=0))
                        if n_shots > 1:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore")
                                stds_vi = np.nanstd(vinter_array, axis=0, ddof=1)
                            U_inter_plot = list(stds_vi * self._get_student_t(n_shots) / np.sqrt(n_shots))
                        else: U_inter_plot = [0.0] * 3
                    else:
                        if 0 <= idx < len(vinter_matrix):
                            Y_inter_plot = list(vinter_matrix[idx])
                        else: Y_inter_plot = [np.nan] * 3
                        U_inter_plot = [0.0] * 3
            
            X_all = list(X_main_plot) + list(X_inter_plot)
            Y_all = list(Y_main_plot) + list(Y_inter_plot)
            
            valid_pts = [(x, y) for x, y in zip(X_all, Y_all) if not np.isnan(y)]
            valid_pts.sort(key=lambda p: p[0])
            
            if valid_pts:
                X_line = [p[0] for p in valid_pts]
                Y_line = [p[1] for p in valid_pts]
                
                self.ax.plot(X_line, Y_line, '-', color=ACCENT, alpha=0.5)
                
                lbl_main = f"V\u0304 (n={n_shots})" if self._show_avg_var.get() else f"V Tir n°{idx+1}"
                self.ax.errorbar(X_main_plot, Y_main_plot, yerr=U_main_plot, fmt='o', color=ACCENT, 
                                 ecolor=ERROR, capsize=4, elinewidth=1.5, markeredgewidth=1.5, label=lbl_main)
                                 
                if X_inter_plot:
                    lbl_inter = "V\u0304 inter" if self._show_avg_var.get() else "V inter"
                    self.ax.errorbar(X_inter_plot, Y_inter_plot, yerr=U_inter_plot, fmt='s', color=ACCENT2, 
                                     markerfacecolor=BG2, ecolor=TEXT_DIM, capsize=3, markeredgewidth=1.5, label=lbl_inter)

                if self._show_labels_var.get():
                    for x_val, y_val in zip(X_main_plot, Y_main_plot):
                        if not np.isnan(y_val) and (x_val != 0.0 or add_v0):
                            self.ax.annotate(f"{y_val:.{dec}f} m/s", (x_val, y_val),
                                             textcoords="offset points", xytext=(0, 8), 
                                             ha='center', va='bottom', fontsize=max(6, self.base_size - 1), color=ACCENT)
                    if X_inter_plot:
                        for x_val, y_val in zip(X_inter_plot, Y_inter_plot):
                            if not np.isnan(y_val):
                                self.ax.annotate(f"{y_val:.{dec}f} m/s", (x_val, y_val),
                                                 textcoords="offset points", xytext=(0, -8), 
                                                 ha='center', va='top', fontsize=max(6, self.base_size - 1), color=ACCENT2)

            
            self.ax.legend(loc="upper left", facecolor=BG3, edgecolor=BORDER, labelcolor=TEXT, fontsize=self.base_size)
            self.ax.set_xlim(-10, 3*D + L + 10)
            self.ax.grid(True, linestyle='--', alpha=0.2, color=TEXT_DIM)
            
        except Exception as e:
            print("Erreur graphique :", e)
            
        self.canvas_graph.draw()

    def _export_data(self):
        if not self._raw_history:
            self._append("⚠️ Aucune donnée en mémoire à exporter.\n", ERROR)
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile=f"gauss_{datetime.now().strftime('%H%M%S')}.csv")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8-sig") as f:
                    f.write("OFFSET;S0;E0;L0;S1;E1;L1;S2;E2;L2;S3;E3;L3\n")
                    for raw_line in self._raw_history:
                        f.write(";".join([str(n).replace('.', ',') for n in raw_line]) + "\n")
                self._lbl_log_status.config(text=f"Export réussi ({len(self._raw_history)} tirs)", fg=SUCCESS)
                self._append(f"💾 Exporté dans {os.path.basename(file_path)}\n", SUCCESS)
            except Exception as e: self._append(f"Erreur Export: {e}\n", ERROR)

    def _import_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not file_path: return
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f: lines = f.readlines()
            try: L = float(self._var_l_chariot.get())
            except ValueError:
                self._append("⚠️ Erreur : Paramètre L invalide.\n", ERROR)
                return
            m = 1000000 
            imported = 0
            for line in lines:
                if "OFFSET" in line.upper() or not line.strip(): continue
                parts = line.strip().split(';')
                if len(parts) >= 13:
                    try:
                        nums = [float(p.replace(',', '.')) for p in parts[:13]]
                        self._raw_history.append(nums)
                        current_speeds = []
                        for i in range(4):
                            l = nums[1 + i*3 + 2]
                            if l > 0: current_speeds.append((L/l)*m)
                            else: current_speeds.append(np.nan)
                        self._history.append(current_speeds)
                        imported += 1
                    except ValueError: continue 
            if imported > 0:
                self._lbl_log_status.config(text=f"Données: {len(self._raw_history)}", fg=SUCCESS)
                self._append(f"📂 {imported} tir(s) ajouté(s).\n", SUCCESS)
                self._var_spin.set(str(len(self._history)))
                self._update_displays()
        except Exception as e: self._append(f"Erreur Import: {e}\n", ERROR)

    def _parse_gauss_data(self, text):
        nums =[float(x) for x in re.findall(r'\d+\.?\d*', text)]
        if len(nums) >= 13:
            self._raw_history.append(nums[:13])
            n = len(self._raw_history)
            self._lbl_log_status.config(text=f"Données en mémoire: {n}", fg=SUCCESS)
            try:
                L = float(self._var_l_chariot.get())
                m = 1000000
                current_speeds =[]
                for i in range(4):
                    l = nums[1 + i*3 + 2]
                    if l > 0: current_speeds.append((L/l)*m)
                    else: current_speeds.append(np.nan)
                self._history.append(current_speeds)
                try:
                    curr = int(self._var_spin.get())
                    if curr == n - 1: self._var_spin.set(str(n))
                except: pass
                self._update_displays()
            except: pass

    def _draw_schema(self):
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 100: return
        mid_y, margin = h / 2, 60
        step = (w - 2 * margin) / 3
        self.canvas.create_line(margin-30, mid_y, w-margin+30, mid_y, fill=BORDER, width=2)
        
        n_shots = len(self._history)
        show_avg = self._show_avg_var.get() and n_shots > 0
        
        try:
            L_char = float(self._var_l_chariot.get())
            D_capt = float(self._var_d_capteur.get())
        except ValueError: L_char, D_capt = 20.0, 45.0
            
        time_unit = self._var_time_unit.get()
        if time_unit == "ns": tf = 1.0
        elif time_unit == "µs": tf = 1000.0
        else: tf = 1000000.0
        
        fmt = f".{self._var_decimals.get()}f"
        mult = 1000000 
        
        lh = self.base_size + 4

        for i in range(4):
            x = margin + i * step
            is_active = self._var_active_c[i].get()
            
            box_fill = ACCENT2 if is_active else BG3
            box_out = ACCENT if is_active else BORDER
            text_color = TEXT if is_active else TEXT_DIM
            
            self.canvas.create_rectangle(x-20, mid_y-25, x+20, mid_y+25, fill=box_fill, outline=box_out)
            self.canvas.create_text(x, mid_y, text=f"C{i}", fill=text_color, font=self.font_ui)
            
            ty = mid_y + 40
            
            if not is_active:
                self.canvas.create_text(x, ty+20, text="DÉSACTIVÉ", fill=ERROR, font=self.font_ui)
                if i < 3:
                    is_next_active = self._var_active_c[i+1].get()
                    arrow_col = ACCENT2 if is_next_active else BORDER
                    self.canvas.create_line(x+25, mid_y-25, x+step-25, mid_y-25, arrow=tk.LAST, fill=arrow_col)
                continue
            
            if show_avg:
                S_vals = [raw[1 + i*3] for raw in self._raw_history if len(raw) > 1+i*3]
                E_vals = [raw[2 + i*3] for raw in self._raw_history if len(raw) > 2+i*3]
                L_vals = [raw[3 + i*3] for raw in self._raw_history if len(raw) > 3+i*3 and raw[3 + i*3] > 0]
                V_vals = [h[i] for h in self._history if not np.isnan(h[i])]
                
                mean_S = np.mean(S_vals) if S_vals else np.nan
                u_S    = self._calc_expanded_uncertainty(S_vals)
                mean_E = np.mean(E_vals) if E_vals else np.nan
                u_E    = self._calc_expanded_uncertainty(E_vals)
                mean_L = np.mean(L_vals) if L_vals else np.nan
                u_L    = self._calc_expanded_uncertainty(L_vals)
                mean_V = np.mean(V_vals) if V_vals else np.nan
                u_V    = self._calc_expanded_uncertainty(V_vals)
                
                su_txt = format(u_S/tf, fmt) if not np.isnan(u_S) else "--"
                eu_txt = format(u_E/tf, fmt) if not np.isnan(u_E) else "--"
                lu_txt = format(u_L/tf, fmt) if not np.isnan(u_L) else "--"
                vu_txt = format(u_V, fmt) if not np.isnan(u_V) else "--"
                
                s_txt  = f"S\u0304: {format(mean_S/tf, fmt)} \u00B1 {su_txt} {time_unit}" if not np.isnan(mean_S) else "S\u0304: --"
                e_txt  = f"E\u0304: {format(mean_E/tf, fmt)} \u00B1 {eu_txt} {time_unit}" if not np.isnan(mean_E) else "E\u0304: --"
                dt_txt = f"dT\u0304: {format(mean_L/tf, fmt)} \u00B1 {lu_txt} {time_unit}" if not np.isnan(mean_L) else "dT\u0304: --"
                v_txt  = f"V\u0304: {format(mean_V, fmt)} \u00B1 {vu_txt} m/s" if not np.isnan(mean_V) else "V\u0304: -- m/s"
                
                if i < 3:
                    is_vinter_active = self._var_active_c[i+1].get()
                    vinter_vals =[]
                    if is_vinter_active:
                        for raw in self._raw_history:
                            if len(raw) > 4+i*3:
                                dt = raw[4 + i*3] - raw[2 + i*3]     
                                if dt > 0: vinter_vals.append(((D_capt - L_char) / dt) * mult)
                                
                    mean_vinter = np.mean(vinter_vals) if vinter_vals else np.nan
                    u_vinter    = self._calc_expanded_uncertainty(vinter_vals)
                    viu_txt = format(u_vinter, fmt) if not np.isnan(u_vinter) else "--"
                    vinter_txt = f"➔ V\u0304: {format(mean_vinter, fmt)} \u00B1 {viu_txt} m/s" if not np.isnan(mean_vinter) else "➔ V\u0304: --"
                    
            else:
                if n_shots > 0:
                    try:
                        idx = int(self._var_spin.get()) - 1
                        idx = max(0, min(idx, n_shots - 1))
                    except: idx = n_shots - 1
                    
                    raw = self._raw_history[idx]
                    sv = raw[1 + i*3]
                    ev = raw[2 + i*3]
                    lv = raw[3 + i*3]
                    vv = self._history[idx][i]
                    
                    s_txt  = f"S: {format(sv/tf, fmt)} {time_unit}"
                    e_txt  = f"E: {format(ev/tf, fmt)} {time_unit}"
                    dt_txt = f"dT: {format(lv/tf, fmt)} {time_unit}"
                    v_txt  = f"V: {format(vv, fmt)} m/s" if not np.isnan(vv) else "V: -- m/s"
                    
                    if i < 3:
                        is_vinter_active = self._var_active_c[i+1].get()
                        if is_vinter_active:
                            dt_inter = raw[4 + i*3] - ev
                            if dt_inter > 0:
                                v_val = ((D_capt - L_char) / dt_inter) * mult
                                vinter_txt = f"➔ V: {format(v_val, fmt)} m/s"
                            else: vinter_txt = "➔ V: --"
                        else: vinter_txt = "➔ V: --"
                else:
                    s_txt, e_txt, dt_txt, v_txt = "S: --", "E: --", "dT: --", "V: --"
                    if i < 3: vinter_txt = "➔ V: --"
            
            self.canvas.create_text(x, ty, text=s_txt, fill=TEXT_DIM, font=self.font_small)
            self.canvas.create_text(x, ty+lh, text=e_txt, fill=TEXT_DIM, font=self.font_small)
            self.canvas.create_text(x, ty+lh*2, text=dt_txt, fill=TEXT, font=self.font_small)
            self.canvas.create_text(x, ty+lh*3+4, text=v_txt, fill=SUCCESS, font=self.font_ui)
            
            if i < 3:
                xm = x + step/2
                is_next_active = self._var_active_c[i+1].get()
                arrow_col = ACCENT2 if is_next_active else BORDER
                self.canvas.create_text(xm, mid_y-40, text=vinter_txt, fill=ACCENT, font=self.font_ui)
                self.canvas.create_line(x+25, mid_y-25, x+step-25, mid_y-25, arrow=tk.LAST, fill=arrow_col)

    def _refresh_ports(self):
        ports =[p.device for p in serial.tools.list_ports.comports()]
        self._port_cb["values"] = ports
        if ports: self._port_var.set(ports[0])

    def _toggle_connection(self):
        if self._running: self._running = False
        else: self._connect()

    def _connect(self):
        try:
            self._serial = serial.Serial(self._port_var.get(), int(self._baud_var.get()), timeout=0.1)
            self._running = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            self._btn_connect.config(text="STOP", bg=ERROR)
        except Exception as e: self._append(f"Erreur: {e}\n", ERROR)

    def _read_loop(self):
        while self._running:
            try:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode(errors='replace')
                    self._queue.put(line)
            except: break
        self._btn_connect.config(text="CONNECTER", bg=ACCENT)

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                self._append(msg)
                self._parse_gauss_data(msg)
        except queue.Empty: pass
        self.after(20, self._poll_queue)

    def _append(self, text, color=TEXT):
        self._txt.insert("end", text)
        self._txt.see("end")

    def _on_close(self):
        self._running = False
        self.destroy()

if __name__ == "__main__":
    app = GaussGunMonitor()
    app.mainloop()
