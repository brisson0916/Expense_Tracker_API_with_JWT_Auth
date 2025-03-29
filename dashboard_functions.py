import pandas as pd
import json
import plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from db_models import db, ExpenseEntry

def filter_category_month_year(query, selected_category=None, selected_month=None, selected_year=None):

    if selected_category:
        query = query.where(ExpenseEntry.category == selected_category)

    if selected_year:
        # Filter by year
        year_start = datetime(int(selected_year), 1, 1)
        year_end = datetime(int(selected_year) + 1, 1, 1)  # Start of next year
        query = query.where(ExpenseEntry.expense_date >= year_start,
                            ExpenseEntry.expense_date < year_end)

    if selected_month:
        # Filter by month
        month_start = datetime(int(selected_year), int(selected_month), 1) if selected_year else datetime(
            datetime.now().year, int(selected_month), 1)
        if selected_month == '12':
            month_end = datetime(int(selected_year) + 1, 1, 1) if selected_year else datetime(datetime.now().year + 1,
                                                                                              1, 1)
        else:
            month_end = datetime(int(selected_year), int(selected_month) + 1, 1) if selected_year else datetime(
                datetime.now().year, int(selected_month) + 1, 1)
        query = query.where(ExpenseEntry.expense_date >= month_start,
                            ExpenseEntry.expense_date < month_end)

    #query of expenses, filtered by category and year/month
    all_expenses = db.session.execute(query).scalars().all()

    return all_expenses

def month_and_category_graph(all_expenses):
    #Convert SQL Row Objects to Python Dict, then use list comprehension, then turn into pandas dataframe
    #credit: https://stackoverflow.com/questions/1958219/how-to-convert-sqlalchemy-row-object-to-a-python-dict/
    #credit: https://stackoverflow.com/questions/29525808/sqlalchemy-orm-conversion-to-pandas-dataframe/74548384#74548384
    df = pd.DataFrame([expense.__dict__ for expense in all_expenses])

    #dataframe data manipulation
    df['category'] = df['category'].astype(str).str.title() #category is enum, change to string
    df[['split_enum','category']] = df['category'].str.split('.', expand=True) #expand=True splits strings into separate columns
    df.drop(columns=["_sa_instance_state",'split_enum','id','user_id'], inplace=True)

    df['year_month'] = df['expense_date'].dt.strftime("%B %Y")

    category_df = df.groupby('category', as_index=False)['amount'].sum() #perform aggregation to sum up all entires for each category
    year_month_df = df.groupby('year_month', as_index=False)['amount'].sum()  # perform aggregation to sum up all entires for each month

    #create pie chart, and subplots (side to side) with plotly
    #https://plotly.com/python/pie-charts/#pie-chart-with-plotly-express
    #https://plotly.com/python/subplots/
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{'type': 'bar'}, {'type': 'pie'}]],
        subplot_titles=("Monthly Expenses", "Expenses by Category"))

    fig.add_trace(
        go.Pie(labels=list(category_df['category']), values=list(category_df['amount']), textinfo='label+percent',),
        row=1, col=2
    )

    fig.add_trace(
        go.Bar(x=list(year_month_df['year_month']), y=list(year_month_df['amount']), name="Spending in HKD"),
        row=1, col=1
    )

    fig.update_layout(height=500, width=1200)

    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return graph_json