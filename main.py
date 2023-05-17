import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import RRR_streamlit
st.title("RRR")

uploaded_file = st.file_uploader("Choose a file")
if uploaded_file is not None:
    RRR_streamlit.main(uploaded_file)





