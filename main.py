import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
import csv
import json
import os
import sqlite3
from datetime import date, timedelta
import calendar
from collections import defaultdict

import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ---------------- CONFIG ----------------

APP_NAME = "Student Expense Tracker"
DEVELOPER_WEBSITE = "https://github.com/Jinith1588"
FONT = "Segoe UI"

CURRENCIES = {
    "Malaysian Ringgit": "RM",
    "Indian Rupee": "₹",
    "Kenyan Shilling": "KSh ",
    "US Dollar": "$",
    "Euro": "€",
    "British Pound": "£",
    "Japanese Yen": "¥",
    "Australian Dollar": "A$",
    "Singapore Dollar": "S$",
    "South African Rand": "R",
    "Nigerian Naira": "₦",
    "Pakistani Rupee": "₨",
}

CATEGORIES = [
    "Food", "Transport", "Books", "Rent",
    "Entertainment", "Health", "Shopping", "Other"
]

CHART_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1", "#ff9da7"
]


# ---------------- STORAGE ----------------

def app_data_dir():
    folder = os.path.join(os.path.expanduser("~"), ".student_expense_tracker")
    os.makedirs(folder, exist_ok=True)
    return folder


DB_FILE = os.path.join(app_data_dir(), "expenses.db")
SETTINGS_FILE = os.path.join(app_data_dir(), "settings.json")


def connect_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spent_on TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
    """)
    return conn


def load_settings():
    defaults = {
        "currency": "Malaysian Ringgit",
        "theme": "Dark",
        "monthly_budget": 0.0
    }

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception:
            pass

    return defaults


def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


settings = load_settings()
calendar_year = date.today().year
calendar_month = date.today().month


# ---------------- HELPERS ----------------

def format_money(value):
    symbol = CURRENCIES[settings["currency"]]
    return f"{symbol}{value:,.2f}"


def date_range():
    today = date.today()

    if filter_menu.get() == "This week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()

    if filter_menu.get() == "This month":
        return today.replace(day=1).isoformat(), today.isoformat()

    return None, None


def get_filtered_expenses():
    start, end = date_range()
    conn = connect_db()

    if start:
        rows = conn.execute("""
            SELECT id, spent_on, amount, category, note
            FROM expenses
            WHERE spent_on BETWEEN ? AND ?
            ORDER BY spent_on DESC, id DESC
        """, (start, end)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, spent_on, amount, category, note
            FROM expenses
            ORDER BY spent_on DESC, id DESC
        """).fetchall()

    conn.close()
    return rows


# ---------------- ACTIONS ----------------

def add_expense():
    try:
        amount = float(amount_entry.get())
        if amount <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Invalid amount", "Please enter a positive number.")
        return

    conn = connect_db()
    conn.execute(
        """INSERT INTO expenses
           (spent_on, amount, category, note)
           VALUES (?, ?, ?, ?)""",
        (
            date.today().isoformat(),
            amount,
            category_menu.get(),
            note_entry.get().strip()
        )
    )
    conn.commit()
    conn.close()

    amount_entry.delete(0, "end")
    note_entry.delete(0, "end")
    refresh_all()


    
def delete_expense_by_id(expense_id):
    if not messagebox.askyesno("Delete expense", "Delete this expense?"):
        return

    conn = connect_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()

    refresh_all()


def edit_selected_expense_by_id(expense_id):
    conn = connect_db()
    expense = conn.execute(
        "SELECT spent_on, amount, category, note FROM expenses WHERE id = ?",
        (expense_id,)
    ).fetchone()
    conn.close()

    if not expense:
        messagebox.showerror("Edit expense", "Expense not found.")
        return

    spent_on, amount, category, note = expense

    amount_entry.delete(0, "end")
    amount_entry.insert(0, str(amount))

    category_menu.set(category)

    note_entry.delete(0, "end")
    note_entry.insert(0, note)

    add_button.configure(
        text="Update expense",
        fg_color="#3b82f6",
        hover_color="#2563eb",
        command=lambda: update_expense(expense_id)
    )
    

def update_expense(expense_id):
    try:
        amount = float(amount_entry.get())
        if amount <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Invalid amount", "Please enter a positive number.")
        return

    conn = connect_db()
    conn.execute(
        """UPDATE expenses
           SET amount = ?, category = ?, note = ?
           WHERE id = ?""",
        (
            amount,
            category_menu.get(),
            note_entry.get().strip(),
            expense_id
        )
    )
    conn.commit()
    conn.close()

    amount_entry.delete(0, "end")
    note_entry.delete(0, "end")
    category_menu.set(CATEGORIES[0])

    reset_add_button()
    refresh_all()


def reset_add_button():
    add_button.configure(
        text="Add expense",
        fg_color="#2ecc71",
        hover_color="#27ae60",
        command=add_expense
    )


def save_budget():
    try:
        budget = float(budget_entry.get())
        if budget < 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Invalid budget", "Please enter a valid monthly budget.")
        return

    settings["monthly_budget"] = budget
    save_settings()
    refresh_all()


def export_report():
    rows = get_filtered_expenses()

    if not rows:
        messagebox.showinfo("Export report", "There are no expenses to export.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        initialfile=f"expense_report_{date.today().isoformat()}.csv",
        filetypes=[("CSV file", "*.csv")]
    )

    if not file_path:
        return

    total = sum(row[2] for row in rows)

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Amount", "Category", "Note"])

        for _, spent_on, amount, category, note in rows:
            writer.writerow([spent_on, f"{amount:.2f}", category, note])

        writer.writerow([])
        writer.writerow(["Total", f"{total:.2f}"])

    messagebox.showinfo("Export complete", f"Report saved to:\n{file_path}")


# ---------------- UI REFRESH ----------------

def open_expense_actions(expense_id):
    menu = ctk.CTkToplevel(root)
    menu.title("Expense actions")
    menu.geometry("280x170")
    menu.resizable(False, False)
    menu.attributes("-topmost", True)

    menu.grab_set()

    ctk.CTkLabel(
        menu,
        text="What do you want to do?",
        font=(FONT, 15, "bold")
    ).pack(pady=(20, 14))

    ctk.CTkButton(
        menu,
        text="Edit expense",
        command=lambda: [menu.destroy(), edit_selected_expense_by_id(expense_id)],
        fg_color="#3b82f6",
        hover_color="#2563eb",
        height=38,
        corner_radius=10,
        font=(FONT, 13, "bold")
    ).pack(fill="x", padx=24, pady=6)

    ctk.CTkButton(
        menu,
        text="Delete expense",
        command=lambda: [menu.destroy(), delete_expense_by_id(expense_id)],
        fg_color="#e74c3c",
        hover_color="#c0392b",
        height=38,
        corner_radius=10,
        font=(FONT, 13, "bold")
    ).pack(fill="x", padx=24, pady=6)




def refresh_table():
    for widget in expense_list.winfo_children():
        widget.destroy()

    rows = get_filtered_expenses()
    total = sum(row[2] for row in rows)

    dark = settings["theme"] == "Dark"

    if not rows:
        ctk.CTkLabel(
            expense_list,
            text="No expenses for this period.",
            font=(FONT, 14),
            text_color=("gray40", "gray60")
        ).pack(pady=40)

        total_label.configure(text=f"Total\n{format_money(total)}")
        update_budget_status(total)
        return

    category_colors = {
        "Food": "#ef4444",
        "Transport": "#3b82f6",
        "Books": "#8b5cf6",
        "Rent": "#f59e0b",
        "Entertainment": "#ec4899",
        "Health": "#10b981",
        "Shopping": "#6366f1",
        "Other": "#64748b"
    }

    for expense_id, spent_on, amount, category, note in rows:
        row_card = ctk.CTkFrame(
            expense_list,
            corner_radius=14,
            fg_color=("#ffffff", "#2b2b2b")
        )
        row_card.pack(fill="x", pady=6, padx=4)

        left_area = ctk.CTkFrame(row_card, fg_color="transparent")
        left_area.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        category_badge = ctk.CTkLabel(
            left_area,
            text=category.upper(),
            font=(FONT, 10, "bold"),
            fg_color=category_colors.get(category, "#64748b"),
            text_color="#ffffff",
            corner_radius=8,
            height=22,
            padx=8
        )
        category_badge.pack(anchor="w")

        display_note = note if note else "No note"
        date_text = date.fromisoformat(spent_on).strftime("%d %b %Y")

        ctk.CTkLabel(
            left_area,
            text=display_note,
            font=(FONT, 14, "bold"),
            anchor="w",
            justify="left"
        ).pack(anchor="w", pady=(6, 2))

        ctk.CTkLabel(
            left_area,
            text=date_text,
            font=(FONT, 11),
            text_color=("gray40", "gray60"),
            anchor="w"
        ).pack(anchor="w")

        right_area = ctk.CTkFrame(row_card, fg_color="transparent")
        right_area.pack(side="right", padx=16, pady=14)

        ctk.CTkLabel(
            right_area,
            text=format_money(amount),
            font=(FONT, 17, "bold")
        ).pack(anchor="e")

        expense_menu_button = ctk.CTkButton(
            right_area,
            text="⋯",
            width=34,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=("#e5e7eb", "#3f3f46"),
            text_color=("gray20", "gray70"),
            command=lambda e_id=expense_id: open_expense_actions(e_id)
        )
        expense_menu_button.pack(anchor="e", pady=(6, 0))

    total_label.configure(text=f"Total\n{format_money(total)}")
    update_budget_status(total)


def update_budget_status(total):
    budget = settings["monthly_budget"]

    if budget <= 0:
        budget_label.configure(
            text="Monthly budget not set",
            text_color=("gray30", "gray70")
        )
        return

    remaining = budget - total

    if total > budget:
        budget_label.configure(
            text=f"⚠ Over budget by {format_money(total - budget)}",
            text_color="#ff5555"
        )
    elif remaining <= budget * 0.2:
        budget_label.configure(
            text=f"⚠ Only {format_money(remaining)} left",
            text_color="#ffa726"
        )
    else:
        budget_label.configure(
            text=f"✓ {format_money(remaining)} remaining",
            text_color="#4caf50"
        )


def refresh_summary():
    summary_table.delete(*summary_table.get_children())

    rows = get_filtered_expenses()
    totals = defaultdict(float)

    for _, _, amount, category, _ in rows:
        totals[category] += amount

    grand_total = sum(totals.values())

    for category in CATEGORIES:
        amount = totals.get(category, 0)
        share = (amount / grand_total * 100) if grand_total else 0

        summary_table.insert(
            "",
            "end",
            values=(
                category,
                format_money(amount),
                f"{share:.1f}%"
            )
        )


def refresh_chart():
    chart_ax.clear()
    rows = get_filtered_expenses()

    dark = settings["theme"] == "Dark"
    text_color = "#eaeaea" if dark else "#1f1f1f"
    face_color = "#2b2b2b" if dark else "#ffffff"

    chart_figure.patch.set_facecolor(face_color)
    chart_ax.set_facecolor(face_color)

    if not rows:
        chart_ax.text(
            0.5,
            0.5,
            "Add an expense to see\nyour spending breakdown",
            ha="center",
            va="center",
            fontsize=11,
            color=text_color
        )
        chart_ax.set_axis_off()
    else:
        totals = defaultdict(float)

        for _, _, amount, category, _ in rows:
            totals[category] += amount

        labels = list(totals.keys())
        values = list(totals.values())

        wedges, texts, autotexts = chart_ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            colors=CHART_COLORS[:len(labels)],
            wedgeprops={"linewidth": 1, "edgecolor": face_color},
            textprops={"color": text_color}
        )

        chart_ax.set_title(
            "Spending by category",
            fontsize=11,
            pad=12,
            color=text_color
        )

    chart_canvas.draw()


def refresh_all():
    refresh_table()
    refresh_summary()
    refresh_chart()
    refresh_calendar()


def previous_month():
    global calendar_month, calendar_year

    calendar_month -= 1
    if calendar_month == 0:
        calendar_month = 12
        calendar_year -= 1

    refresh_calendar()


def next_month():
    global calendar_month, calendar_year

    calendar_month += 1
    if calendar_month == 13:
        calendar_month = 1
        calendar_year += 1

    refresh_calendar()


def get_daily_totals():
    start = date(calendar_year, calendar_month, 1).isoformat()

    if calendar_month == 12:
        end = date(calendar_year + 1, 1, 1).isoformat()
    else:
        end = date(calendar_year, calendar_month + 1, 1).isoformat()

    conn = connect_db()
    rows = conn.execute("""
        SELECT spent_on, SUM(amount)
        FROM expenses
        WHERE spent_on >= ? AND spent_on < ?
        GROUP BY spent_on
    """, (start, end)).fetchall()
    conn.close()

    return {row[0]: row[1] for row in rows}


def show_day_expenses(day_iso):
    conn = connect_db()
    rows = conn.execute("""
        SELECT amount, category, note
        FROM expenses
        WHERE spent_on = ?
        ORDER BY id DESC
    """, (day_iso,)).fetchall()
    conn.close()

    if not rows:
        day_details.configure(text=f"No expenses on {day_iso}.")
        return

    total = sum(row[0] for row in rows)
    lines = [f"{day_iso} — Total: {format_money(total)}", ""]

    for amount, category, note in rows:
        note_text = f" — {note}" if note else ""
        lines.append(f"• {format_money(amount)} — {category}{note_text}")

    day_details.configure(text="\n".join(lines))


def refresh_calendar():
    for widget in calendar_grid.winfo_children():
        widget.destroy()

    month_name = calendar.month_name[calendar_month]
    calendar_title.configure(text=f"{month_name} {calendar_year}")

    daily_totals = get_daily_totals()
    weeks = calendar.Calendar().monthdatescalendar(calendar_year, calendar_month)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for column, day_name in enumerate(day_names):
        ctk.CTkLabel(
            calendar_grid,
            text=day_name,
            font=(FONT, 13, "bold")
        ).grid(row=0, column=column, sticky="nsew", padx=4, pady=4)

    dark = settings["theme"] == "Dark"

    for row_index, week in enumerate(weeks, start=1):
        for column_index, day in enumerate(week):
            day_iso = day.isoformat()
            spent = daily_totals.get(day_iso, 0)

            is_current_month = day.month == calendar_month
            is_today = day == date.today()

            button_text = day.strftime("%d")

            if spent:
                button_text += f"\n{format_money(spent)}"

            if is_today:
                bg = "#3b82f6"
                hover = "#2563eb"
                fg = "#ffffff"
            elif spent:
                bg = "#2ecc71" if not dark else "#1f6f43"
                hover = "#27ae60" if not dark else "#166534"
                fg = "#ffffff"
            else:
                bg = "#ffffff" if not dark else "#2b2b2b"
                hover = "#f1f3f5" if not dark else "#333333"
                fg = "#1f1f1f" if not dark else "#eaeaea"

            day_button = ctk.CTkButton(
                calendar_grid,
                text=button_text,
                command=lambda d=day_iso: show_day_expenses(d),
                corner_radius=10,
                height=72,
                font=(FONT, 12),
                fg_color=bg,
                hover_color=hover,
                text_color=fg
            )

            if not is_current_month:
                day_button.configure(
                    state="disabled",
                    fg_color="transparent",
                    text_color="gray"
                )

            day_button.grid(
                row=row_index,
                column=column_index,
                sticky="nsew",
                padx=4,
                pady=4
            )

    for column in range(7):
        calendar_grid.grid_columnconfigure(column, weight=1)

    for row in range(len(weeks) + 1):
        calendar_grid.grid_rowconfigure(row, weight=1)


def apply_table_theme():
    dark = settings["theme"] == "Dark"

    row_bg = "#2b2b2b" if dark else "#ffffff"
    row_fg = "#eaeaea" if dark else "#1f1f1f"
    heading_bg = "#333333" if dark else "#f1f3f5"
    heading_fg = "#eaeaea" if dark else "#1f1f1f"

    table_style.theme_use("clam")

    table_style.configure(
        "Treeview",
        rowheight=36,
        font=(FONT, 12),
        background=row_bg,
        fieldbackground=row_bg,
        foreground=row_fg,
        borderwidth=0
    )

    table_style.configure(
        "Treeview.Heading",
        font=(FONT, 12, "bold"),
        background=heading_bg,
        foreground=heading_fg,
        padding=10,
        borderwidth=0
    )

    table_style.map(
        "Treeview",
        background=[("selected", "#3b82f6")],
        foreground=[("selected", "#ffffff")]
    )

    table_style.map(
        "Treeview.Heading",
        background=[("active", heading_bg)],
        foreground=[("active", heading_fg)]
    )


def change_currency(choice):
    settings["currency"] = choice
    save_settings()
    refresh_all()


def change_theme(choice):
    settings["theme"] = choice
    save_settings()

    ctk.set_appearance_mode(choice.lower())
    apply_table_theme()
    refresh_all()


def change_filter(choice):
    refresh_all()


# ---------------- APP SETUP ----------------

ctk.set_appearance_mode(settings["theme"].lower())
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title(f"{APP_NAME}")
root.geometry("1300x820")
root.minsize(1150, 760)

# Header
header = ctk.CTkFrame(root, fg_color="transparent")
header.pack(fill="x", padx=28, pady=(24, 12))

ctk.CTkLabel(
    header,
    text=APP_NAME,
    font=(FONT, 26, "bold")
).pack(side="left")

ctk.CTkLabel(
    header,
    text="Track your spending clearly",
    font=(FONT, 13),
    text_color=("gray30", "gray70")
).pack(side="left", padx=14, pady=(10, 0))

# Settings card
settings_card = ctk.CTkFrame(root, corner_radius=16)
settings_card.pack(fill="x", padx=28, pady=10)

settings_inner = ctk.CTkFrame(settings_card, fg_color="transparent")
settings_inner.pack(fill="x", padx=20, pady=18)

ctk.CTkLabel(
    settings_inner,
    text="Currency",
    font=(FONT, 13, "bold")
).grid(row=0, column=0, sticky="w")

currency_menu = ctk.CTkOptionMenu(
    settings_inner,
    values=list(CURRENCIES.keys()),
    command=change_currency,
    width=210,
    height=36,
    font=(FONT, 13)
)
currency_menu.set(settings["currency"])
currency_menu.grid(row=1, column=0, padx=(0, 24), pady=(8, 0), sticky="w")

ctk.CTkLabel(
    settings_inner,
    text="Theme",
    font=(FONT, 13, "bold")
).grid(row=0, column=1, sticky="w")

theme_menu = ctk.CTkOptionMenu(
    settings_inner,
    values=["Light", "Dark"],
    command=change_theme,
    width=130,
    height=36,
    font=(FONT, 13)
)
theme_menu.set(settings["theme"])
theme_menu.grid(row=1, column=1, padx=(0, 24), pady=(8, 0), sticky="w")

ctk.CTkLabel(
    settings_inner,
    text="Monthly budget",
    font=(FONT, 13, "bold")
).grid(row=0, column=2, sticky="w")

budget_entry = ctk.CTkEntry(
    settings_inner,
    width=140,
    height=36,
    font=(FONT, 13),
    placeholder_text="0.00"
)
budget_entry.insert(0, str(settings["monthly_budget"]))
budget_entry.grid(row=1, column=2, padx=(0, 10), pady=(8, 0), sticky="w")

ctk.CTkButton(
    settings_inner,
    text="Save",
    command=save_budget,
    width=90,
    height=36,
    corner_radius=8,
    font=(FONT, 13, "bold")
).grid(row=1, column=3, pady=(8, 0), sticky="w")

# Add expense card
add_card = ctk.CTkFrame(root, corner_radius=16)
add_card.pack(fill="x", padx=28, pady=10)

add_inner = ctk.CTkFrame(add_card, fg_color="transparent")
add_inner.pack(fill="x", padx=20, pady=18)

ctk.CTkLabel(
    add_inner,
    text="Amount",
    font=(FONT, 13, "bold")
).grid(row=0, column=0, sticky="w")

amount_entry = ctk.CTkEntry(
    add_inner,
    width=150,
    height=38,
    font=(FONT, 13),
    placeholder_text="0.00"
)
amount_entry.grid(row=1, column=0, padx=(0, 20), pady=(8, 0), sticky="w")

ctk.CTkLabel(
    add_inner,
    text="Category",
    font=(FONT, 13, "bold")
).grid(row=0, column=1, sticky="w")

category_menu = ctk.CTkOptionMenu(
    add_inner,
    values=CATEGORIES,
    width=180,
    height=38,
    font=(FONT, 13)
)
category_menu.set(CATEGORIES[0])
category_menu.grid(row=1, column=1, padx=(0, 20), pady=(8, 0), sticky="w")

ctk.CTkLabel(
    add_inner,
    text="Note",
    font=(FONT, 13, "bold")
).grid(row=0, column=2, sticky="w")

note_entry = ctk.CTkEntry(
    add_inner,
    width=320,
    height=38,
    font=(FONT, 13),
    placeholder_text="Optional note"
)
note_entry.grid(row=1, column=2, padx=(0, 20), pady=(8, 0), sticky="w")

add_button = ctk.CTkButton(
    add_inner,
    text="Add expense",
    command=add_expense,
    width=140,
    height=38,
    corner_radius=10,
    font=(FONT, 13, "bold"),
    fg_color="#2ecc71",
    hover_color="#27ae60"
)
add_button.grid(row=1, column=3, pady=(8, 0), sticky="w")

# Filter card
filter_card = ctk.CTkFrame(root, corner_radius=16)
filter_card.pack(fill="x", padx=28, pady=10)

filter_inner = ctk.CTkFrame(filter_card, fg_color="transparent")
filter_inner.pack(fill="x", padx=20, pady=14)

ctk.CTkLabel(
    filter_inner,
    text="Show expenses",
    font=(FONT, 13, "bold")
).pack(side="left")

filter_menu = ctk.CTkOptionMenu(
    filter_inner,
    values=["This week", "This month", "All time"],
    command=change_filter,
    width=160,
    height=36,
    font=(FONT, 13)
)
filter_menu.set("This month")
filter_menu.pack(side="left", padx=14)

ctk.CTkButton(
    filter_inner,
    text="Export report",
    command=export_report,
    width=140,
    height=36,
    corner_radius=8,
    font=(FONT, 13, "bold"),
    fg_color="#3b82f6",
    hover_color="#2563eb"
).pack(side="left", padx=10)

# Main dashboard
main_area = ctk.CTkTabview(
    root,
    corner_radius=16
)
main_area.pack(fill="both", expand=True, padx=28, pady=10)

main_area.add("Dashboard")
main_area.add("Calendar")

# Developer watermark
for tab_name in ["Dashboard", "Calendar"]:
    ctk.CTkButton(
        main_area.tab(tab_name),
        text="© 2026 Jinith Baman",
        font=(FONT, 11),
        fg_color="transparent",
        hover_color=("#e5e7eb", "#333333"),
        text_color=("gray50", "gray50"),
        border_width=0,
        corner_radius=6,
        command=lambda: webbrowser.open(DEVELOPER_WEBSITE)
    ).place(
        relx=0.99,
        rely=0.99,
        anchor="se"
    )

# Expense list card
expense_card = ctk.CTkFrame(
    main_area.tab("Dashboard"),
    corner_radius=16
)
expense_card.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(0, 14)
)

expense_header = ctk.CTkFrame(expense_card, fg_color="transparent")
expense_header.pack(fill="x", padx=20, pady=(18, 10))

ctk.CTkLabel(
    expense_header,
    text="Expenses",
    font=(FONT, 18, "bold")
).pack(side="left")

expense_list = ctk.CTkScrollableFrame(
    expense_card,
    fg_color="transparent"
)
expense_list.pack(
    fill="both",
    expand=True,
    padx=16,
    pady=(0, 18)
)

# Summary card
summary_card = ctk.CTkFrame(main_area.tab("Dashboard"), corner_radius=16)
summary_card.pack(side="right", fill="x", padx=(14, 0), pady=(0, 14))

ctk.CTkLabel(
    summary_card,
    text="Category summary",
    font=(FONT, 16, "bold")
).pack(anchor="w", padx=20, pady=(18, 10))

summary_columns = ("Category", "Total", "Share")
summary_table = ttk.Treeview(
    summary_card,
    columns=summary_columns,
    show="headings",
    height=5
)

summary_table.heading("Category", text="Category")
summary_table.heading("Total", text="Total")
summary_table.heading("Share", text="Share")

summary_table.column("Category", width=130)
summary_table.column("Total", width=120, anchor="e")
summary_table.column("Share", width=80, anchor="e")

summary_table.pack(fill="x", padx=20, pady=(0, 20))

# Chart card
chart_card = ctk.CTkFrame(main_area.tab("Dashboard"), corner_radius=16)
chart_card.pack(side="right", fill="both", expand=True, padx=(14, 0))

ctk.CTkLabel(
    chart_card,
    text="Spending breakdown",
    font=(FONT, 16, "bold")
).pack(anchor="w", padx=20, pady=(18, 8))

chart_figure = Figure(figsize=(4.2, 3.2), dpi=100)
chart_ax = chart_figure.add_subplot(111)

chart_canvas = FigureCanvasTkAgg(chart_figure, master=chart_card)
chart_canvas.get_tk_widget().pack(
    fill="both",
    expand=True,
    padx=16,
    pady=(0, 18)
)






# Calendar tab
calendar_tab = main_area.tab("Calendar")

calendar_header = ctk.CTkFrame(calendar_tab, fg_color="transparent")
calendar_header.pack(fill="x", padx=20, pady=(20, 10))

ctk.CTkButton(
    calendar_header,
    text="<",
    width=44,
    height=36,
    corner_radius=8,
    command=previous_month
).pack(side="left")

calendar_title = ctk.CTkLabel(
    calendar_header,
    text="",
    font=(FONT, 20, "bold")
)
calendar_title.pack(side="left", padx=20)

ctk.CTkButton(
    calendar_header,
    text=">",
    width=44,
    height=36,
    corner_radius=8,
    command=next_month
).pack(side="left")

calendar_grid = ctk.CTkFrame(calendar_tab, corner_radius=16)
calendar_grid.pack(fill="both", expand=True, padx=20, pady=(0, 20))

day_details = ctk.CTkLabel(
    calendar_tab,
    text="Select a day to see its expenses.",
    font=(FONT, 14),
    justify="left",
    anchor="w"
)
day_details.pack(fill="x", padx=20, pady=(0, 20))

# Bottom status bar
bottom_bar = ctk.CTkFrame(root, corner_radius=16)
bottom_bar.pack(fill="x", padx=28, pady=(10, 24))


total_label = ctk.CTkLabel(
    bottom_bar,
    text="Total\n0",
    font=(FONT, 17, "bold"),
    justify="left"
)
total_label.pack(side="left", padx=24, pady=16)

budget_label = ctk.CTkLabel(
    bottom_bar,
    text="Monthly budget not set",
    font=(FONT, 15, "bold")
)
budget_label.pack(side="left", padx=24, pady=16)

# Footer credit
footer = ctk.CTkFrame(root, fg_color="transparent")
footer.pack(fill="x", padx=28, pady=(0, 14))

ctk.CTkLabel(
    footer,
    text="© 2026 Jinith Baman • Student Expense Tracker",
    font=(FONT, 11),
    text_color=("gray40", "gray60")
).pack()

# ---------------- INITIALIZE STYLES ----------------

table_style = ttk.Style()
apply_table_theme()


# ---------------- START ----------------

refresh_all()
root.mainloop()