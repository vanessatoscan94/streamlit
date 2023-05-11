# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# IMPORT
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import random
import seaborn as sns
import streamlit as st

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# FUNCTIONS
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def extract_results(uploaded_file,data_sheets):

    # Initialize dict for results
    kpis = dict()
    normalized_kpis = dict()



    # results we want to extract
    column_names = ["disturbance_start_index", "disturbance_start_month", "disturbance_end_index", "disturbance_end_month", "disturbance_magnitude",
                    "otd_effect_start_index", "otd_effect_start_month", "otd_effect_end_index", "otd_effect_end_month", "otd_effect_initial_value", "otd_effect_min_value", "otd_effect_max_value",
                    "cost_effect_start_index", "cost_effect_start_month", "cost_effect_end_index", "cost_effect_end_month", "cost_effect_initial_value", "cost_effect_min_value", "cost_effect_max_value",
                    "capacity_effect_start_index", "capacity_effect_start_month", "capacity_effect_end_index", "capacity_effect_end_month", "capacity_effect_initial_value", "capacity_effect_min_value", "capacity_effect_max_value"]
    results = pd.DataFrame(columns=column_names)

    # loop through all sheets
    for data_sheet in data_sheets:
        sheet_values = dict()

        # read excel
        df = pd.read_excel(uploaded_file, sheet_name=data_sheet)

        # detect the column with disturbance
        column_with_disturbance = detect_column_with_disturbance(df)

        # detect the disturbance
        sheet_values["disturbance_start_index"], \
            sheet_values["disturbance_start_month"], \
            sheet_values["disturbance_end_index"], \
            sheet_values["disturbance_end_month"], \
            sheet_values["disturbance_magnitude"] = detect_disturbance(df, column_with_disturbance)

        # detect effect on otd
        column_with_effect = "Inventory Management.KPI: OTD: Delivery quota"
        threshold_lb = 0.99
        threshold_ub = 1.01
        sheet_values["otd_effect_start_index"], \
            sheet_values["otd_effect_start_month"], \
            sheet_values["otd_effect_end_index"], \
            sheet_values["otd_effect_end_month"], \
            sheet_values["otd_effect_initial_value"], \
            sheet_values["otd_effect_min_value"], \
            sheet_values["otd_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect, threshold_lb, threshold_ub)

        # detect effect on cost
        column_with_effect = "Bewertung.KPI Relativer Kostenanteil an Umsatz"
        threshold_lb = 0.94
        threshold_ub = 1.06
        sheet_values["cost_effect_start_index"], \
            sheet_values["cost_effect_start_month"], \
            sheet_values["cost_effect_end_index"], \
            sheet_values["cost_effect_end_month"], \
            sheet_values["cost_effect_initial_value"], \
            sheet_values["cost_effect_min_value"], \
            sheet_values["cost_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect, threshold_lb, threshold_ub)

                # detect effect on capacity
        column_with_effect = "Bewertung.KPI Relativer Kostenanteil an Umsatz"
        threshold_lb = 0.99
        threshold_ub = 1.01
        sheet_values["capacity_effect_start_index"], \
            sheet_values["capacity_effect_start_month"], \
            sheet_values["capacity_effect_end_index"], \
            sheet_values["capacity_effect_end_month"], \
            sheet_values["capacity_effect_initial_value"], \
            sheet_values["capacity_effect_min_value"], \
            sheet_values["capacity_effect_max_value"] = detect_effect(df, sheet_values, column_with_effect,threshold_lb, threshold_ub)

        results.loc[data_sheet] = sheet_values

    return results

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_kpis(results):

    # kpis = dict()

    file_kpis = dict()

    # calculate robustness
    file_kpis["otd_robustness"], \
        file_kpis["cost_robustness"], \
        file_kpis["capacity_robustness"] = calculate_robustness(results)

    # calculate recover_rapidity
    file_kpis["otd_recover_rapidity"], \
        file_kpis["cost_recover_rapidity"], \
        file_kpis["capacity_recover_rapidity"] = calculate_recover_rapidity(results)

    kpis = pd.DataFrame(file_kpis)

    return kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def normalize_kpis(kpis):

    normalized_file_kpis = dict()
    for column in kpis.columns:
        normalized_file_kpis[column] = calculate_normalized_kpis(kpis[column])

    normalized_kpis = pd.DataFrame(normalized_file_kpis)

    return normalized_kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_column_with_disturbance(df):

    all_columns_with_disturbance = ["Zulieferer.Indicator Abbau Lieferant",
                                    "Zulieferer.Ungeplante Ausfälle[Supplier A]",
                                    "Zulieferer.Ungeplante Ausfälle[Supplier B]",
                                    "Zulieferer.Magnitude Ausfall Produktionskapazität[Supplier A]",
                                    "Zulieferer.Magnitude Ausfall Produktionskapazität[Supplier B]",
                                    "Production capacity.Ausfall eigene Kapazität",
                                    "Market / Competition.STEP Nachfrage",
                                    "Market / Competition.Nachfrage"]

    columns_with_disturbance = list()
    for column in all_columns_with_disturbance:
        if df[column].nunique() != 1:
            columns_with_disturbance.append(column)

    if len(columns_with_disturbance) == 1:
        column_with_disturbance = columns_with_disturbance[0]
    elif len(columns_with_disturbance) > 1:
        # TODO: Ist es immer die Letzte?
        column_with_disturbance = columns_with_disturbance[-1]
    else:
        raise ValueError("No disturbance detected!")

    return column_with_disturbance

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_disturbance(df,column_with_disturbance):

    # Get initial month
    initial_month = df.loc[0, 'month']
    # Get initial value of disturbance-column
    initial_value = df.loc[df['month'] == initial_month, column_with_disturbance].iloc[0]

    # Index and month of the first row where the value of the disturbance is greater than the initial value
    start_index = df.loc[df[column_with_disturbance] > initial_value].index[0]
    start_month = df['month'].iloc[start_index]
    # Index and month of the last row where the value of the disturbance is greater than the initial value
    end_index = df.loc[df[column_with_disturbance] > initial_value].index[-1]
    end_month = df['month'].iloc[end_index]

    # Get magnitude of disturbance
    # TODO: Is disturbance always an increase? (e.g. column "Nachfrage" -> decrease?)
    magnitude = df[column_with_disturbance].max()

    # IDEA GIAN... not needed so far...
    min_value = df[column_with_disturbance].min()
    max_value = df[column_with_disturbance].max()

    return start_index,start_month,end_index,end_month,magnitude

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def detect_effect(df,sheet_values,column_with_effect,threshold_lb,threshold_ub):

    initial_month = df.loc[0, 'month']
    initial_value = df.loc[df['month'] == initial_month, column_with_effect].iloc[0]

    # Index and month of first row after the disturbance start where the value of the effect is not equal the initial value
    start_index = df.loc[(df.index >= sheet_values["disturbance_start_index"]) & (df[column_with_effect] != initial_value)].index[0]
    start_month = df['month'].iloc[start_index]

    # Index and month of last row after the disturbance end where the value of the effect is not inside the range to call the effect as over
    # TODO : GIAN : index of last row where effect not equal to initial value, or row where effect is back to initial value?
    end_index = df.loc[(df.index >= sheet_values["disturbance_end_index"]) & (df[column_with_effect] < threshold_lb) | (df[column_with_effect] > threshold_ub)].index[-1]
    end_month = df['month'].iloc[end_index]

    # IDEA GIAN
    min_value = df.loc[(df.index >= start_index) & (df.index <= end_index),column_with_effect].min()
    max_value = df.loc[(df.index >= start_index) & (df.index <= end_index),column_with_effect].max()

    return start_index,start_month,end_index,end_month,initial_value,min_value,max_value

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_hardness(results):

    # Parameter
    # tc := time when the disturbance starts to affect the system
    # TODO: Start der Disturbance oder Start des Effekts?
    tc = results["disturbance_start_month"]
    # td := time when the disturbance stops
    td = results["disturbance_end_month"]
    # magnitude (delta) := magnitude of disturbance
    # TODO: Wie genau ist die "magnitude" zu messen?
    magnitude = results["disturbance_magnitude"]

    # ··················································································································

    # Calculate disturbance
    # disturbance (sigma) := disturbance affecting the syste
    # TODO: Gemäss Paper, sind disturbance und hardness m.E. dasselbe... (sigma und sigma_H)
    disturbance = magnitude * (td - tc)

    # ··················································································································

    # calculate otd_hardness
    otd_hardness = disturbance * (td - tc)

    # ··················································································································

    # calculate cost_hardness
    cost_hardness = disturbance * (td - tc)

    # ··················································································································

    # calculate capacity_hardness
    capacity_hardness = disturbance * (td - tc)

    # ··················································································································

    return otd_hardness,cost_hardness,capacity_hardness

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_robustness(results):

    # Parameter
    # magnitude (sigma) := magnitude of disturbance
    magnitude = results["disturbance_magnitude"]

    # ··················································································································

    # calculate otd_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["otd_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["otd_effect_min_value"]
    otd_robustness = magnitude / (A - B)

    # ··················································································································

    # calculate cost_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["cost_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["cost_effect_min_value"]
    cost_robustness = magnitude / (A - B)

    # ··················································································································

    # calculate capacity_robustness
    # A := ???
    # TODO: Definition fehlt
    A = results["capacity_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["capacity_effect_min_value"]
    capacity_robustness = magnitude / (A - B)

    # ··················································································································

    return otd_robustness,cost_robustness,capacity_robustness

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_recover_rapidity(results):
    """recover rapidity := the average rate at which a system returns to equilibrium after a disturbance."""

    # Parameter
    # td := time when the disturbance stops
    td = results["disturbance_end_month"]

    # ··················································································································

    # calculate otd_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["otd_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["otd_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["otd_effect_min_value"]
    otd_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    # calculate cost_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["cost_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["cost_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["cost_effect_min_value"]
    cost_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    # calculate capacity_recover_rapidity
    # tf := time when the system fully recovers
    tf = results["capacity_effect_end_month"]
    # A := ???
    # TODO: Definition fehlt!
    A = results["capacity_effect_initial_value"]
    # B := ???
    # TODO: Definition fehlt!
    # TODO: So übernommen von Daniel -> Immer ein Minimum oder könnte es auch ein Maximum sein?
    B = results["capacity_effect_min_value"]
    capacity_recover_rapidity = (A - B) / (tf - td)

    # ··················································································································

    return otd_recover_rapidity, cost_recover_rapidity, capacity_recover_rapidity

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def calculate_normalized_kpis(kpis):

    min_value = kpis.min()
    max_value = kpis.max()

    n_kpis = kpis.apply(lambda x: (x - min_value) / (max_value - min_value))

    return n_kpis

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def verification_plot(df,column_with_disturbance,disturbance,effect_on_otd,effect_on_cost,effect_on_capacity):

    # Disturbance
    plt.plot(df["month"],df[column_with_disturbance],color="blue")
    plt.scatter(disturbance["start_month"], 0, color="blue")
    plt.scatter(disturbance["end_month"], 0, color="blue")
    # Effect on otd
    plt.plot(df["month"],df["Inventory Management.KPI: OTD: Delivery quota"],color="red",label="OTD")
    plt.scatter(effect_on_otd["start_month"], effect_on_otd["initial_value"], color="red")
    plt.scatter(effect_on_otd["end_month"], effect_on_otd["initial_value"], color="red")
    # Effect on cost
    plt.plot(df["month"],df["Bewertung.KPI Relativer Kostenanteil an Umsatz"],color="orange",label="Cost")
    plt.scatter(effect_on_cost["start_month"], effect_on_cost["initial_value"], color="orange")
    plt.scatter(effect_on_cost["end_month"], effect_on_cost["initial_value"], color="orange")
    # Effect on capacity
    plt.plot(df["month"],df["Production capacity.KPI Yield"],color="green")
    plt.scatter(effect_on_capacity["start_month"], effect_on_capacity["initial_value"], color="green",label="Capacity")
    plt.scatter(effect_on_capacity["end_month"], effect_on_capacity["initial_value"], color="green")
    plt.legend()
    plt.show()

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

def create_heatmaps(kpis):

    # Define custom color map
    cmap = sns.diverging_palette(150, 275, s=80, l=50, n=9, as_cmap=True)

    # create subplots
    fig, axes = plt.subplots(ncols=3, figsize=(10, 5))

        # Create heatmap with custom color map
    df = kpis.loc[:, ['otd_robustness', 'otd_recover_rapidity']]
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[0])
    axes[0].set_title('KPIs on OTD', fontsize=12)

    # Create heatmap with custom color map
    df = kpis.loc[:, ['cost_robustness', 'cost_recover_rapidity']]
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[1])
    axes[1].set_title('KPIs on cost', fontsize=12)

    # Create heatmap with custom color map
    df = kpis.loc[:, ['capacity_robustness', 'capacity_recover_rapidity']]
    sns.heatmap(df, annot=True, cbar=True, vmin=0, vmax=1, ax=axes[2])
    axes[2].set_title('KPIs on capacity', fontsize=12)

    plt.suptitle("Resultate")
    plt.tight_layout()
    #plt.show()
    st.write(fig)

# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# MAIN
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def main():

    # Define path, filename and sheet of excel-files
    data_path = Path.cwd() / "Data"
    data_filenames = ["C1","C3"]
    data_sheets = ["P0","P1","P2","P3","P4","P5","P7","P9"]

    # extract results
    results = extract_results(data_path,data_filenames,data_sheets)

    # calculate kpis
    kpis = calculate_kpis(results)

    # normalize the kpis
    normalized_kpis = normalize_kpis(kpis)

    # create heatmaps
    create_heatmaps(normalized_kpis)

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# IF __NAME__ == "__MAIN__"
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

if __name__ == "__main__":
    main()
