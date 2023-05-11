import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import RRR
st.title("RRR")

uploaded_file = st.file_uploader("Choose a file")
if uploaded_file is not None:

    # Define path, filename and sheet of excel-files
    data_sheets = ["P0", "P1", "P2", "P3", "P4", "P5", "P7", "P9"]

    # extract results
    results = RRR.extract_results(uploaded_file, data_sheets)

    # calculate kpis
    kpis = RRR.calculate_kpis(results)

    # normalize the kpis
    normalized_kpis = RRR.normalize_kpis(kpis)

    # create heatmaps
    RRR.create_heatmaps(normalized_kpis)



