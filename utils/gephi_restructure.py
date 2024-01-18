import psycopg2
import sys
import os
import boto3
import pandas as pd
from psycopg2.extensions import connection
from typing import List, Tuple, Dict, Optional
import logging

# Logging configuration
logging.basicConfig(filename='../logs/runtime_logs.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# PostgreSQL config
ConfigDict = Dict[str, str]

db_params: ConfigDict = {
    'dbname': 'pdf2qadev',
    'user': 'mathews.km@tiiqunetwork.onmicrosoft.com',
    'host': 'pdf2qa-dev20231229171910310300000001.clfojyqicnb4.eu-west-2.rds.amazonaws.com',
    'region': 'eu-west-2',
    'port': '5432'
}

ENDPOINT="pdf2qa-dev20231229171910310300000001.clfojyqicnb4.eu-west-2.rds.amazonaws.com"
PORT="5432"
USER="mathews.km@tiiqunetwork.onmicrosoft.com"
REGION="eu-west-2"
DBNAME="pdf2qadev"

def db_connect(db_params: ConfigDict) -> Optional[connection]:
    '''
    Establish a connection to the PostgreSQL db.
    '''
    #os.environ['AWS_CONFIG_FILE'] = '~/.aws/config'
    #session = boto3.Session(profile_name='RDSCredsTestProfile')
    try:
        session = boto3.Session(
            aws_access_key_id='AKIARTBJEWVJGRS2ZO72',
            aws_secret_access_key='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',
            region_name='eu-west-2'
            )
        
        client = session.client('rds')

        token = client.generate_db_auth_token(DBHostname=ENDPOINT, 
                                            Port=PORT, 
                                            DBUsername=USER, 
                                            Region=REGION)
        logging.info('Boto session created.')
        #db_params['token'] = token
    except Exception as err:
        logging.info('Something went wrong. . .', err)
        return None

    try:
        conn: connection = psycopg2.connect(host=ENDPOINT, port=PORT, database=DBNAME, user=USER, password=token)
        logging.info('Database connection established.')
        return conn
    except psycopg2.Error as err:
        logging.error(f'Error connecting to the PostgreSQL database: {err}')
        return None

def db_pull(conn: connection) -> Optional[pd.DataFrame]:
    '''
    Pull the data from the database.
    '''

    # TODO: Need to add where clause to fetch new records
    sql_query: str = """
            SELECT
                s.name as SubTopic,
                t.name as Topic,
                m.name as MacroTopic,
            FROM
                qnaSubtopic s
            JOIN
                Topic t ON s.topicid = t.id
            JOIN
                Macrotopic m ON t.macrotopicid = m.id
            WHERE
                
        """

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query)
            df: pd.DataFrame = pd.DataFrame(cur.fetchall(), columns=[desc for desc in cur.description()])
            logging.info('Data fetched successfully.')
            return df
    except psycopg2.Error as err:
        logging.error(f'Error fetching the data from the PostgreSQL database: {err}')
        return None
    
def print_results(results: List[Tuple]) -> None:
    '''
    Log the results fetched from the database.
    '''
    for row in results:
        logging.info(f"Row: {row}")

def db_push(conn: connection, df_nodes: pd.DataFrame, df_edges: pd.DataFrame) -> bool:
    '''
    Push nodes and edges DataFrames to the GephiNode and GephiEdges tables in the database.
    '''
    try:
        with conn.cursor() as cur:
            # Push nodes to GephiNode table
            for _, row in df_nodes.iterrows():
                cur.execute("INSERT INTO GephiNode (nodeLabel) VALUES (%s);", (row['nodeLabel'],))

            # Push edges to GephiEdges table
            for _, row in df_edges.iterrows():
                cur.execute("INSERT INTO GephiEdges (source, target) VALUES (%s, %s);", (row['Source'], row['Target']))

            # Commit the changes
            conn.commit()

            logging.info('Data pushed successfully.')
            return True
    except psycopg2.Error as err:
        logging.error(f'Error pushing data to the database: {err}')
        return False
 

def gephi_restructure(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    '''
    Restructure the data for Gephi and return nodes and edges DataFrames.
    '''
    # Create a unique set of nodes from topics, subtopics, and macrotopics
    unique_nodes = set(df['SubTopic']) | set(df['Topic']) | set(df['MacroTopic'])

    # Create a DataFrame for nodes
    nodes_df = pd.DataFrame(list(unique_nodes), columns=['nodeLabel'])

    # Create a DataFrame for edges
    edges_df = pd.DataFrame(columns=['Source', 'Target', 'Type'])

    # Iterate through the DataFrame to create edges
    for index, row in df.iterrows():
        source_node = row['MacroTopic']
        target_node = row['Topic']
        edges_df = edges_df.append({'Source': source_node, 'Target': target_node, 'Type': 'undirected'}, ignore_index=True)

        source_node = row['Topic']
        target_node = row['SubTopic']
        edges_df = edges_df.append({'Source': source_node, 'Target': target_node, 'Type': 'undirected'}, ignore_index=True)

    return nodes_df, edges_df

def main():
    # Establish the connection to the database
    conn = db_connect(db_params)

    if conn:
        df_data = db_pull(conn)

        if df_data is not None and not df_data.empty:
            df_nodes, df_edges = gephi_restructure(df_data)

            # Pushing the data backl to the database 
            db_push(conn, df_nodes, df_edges)
    
    # Close the connection
    conn.close()
    logging.info('Closing the database connection. . .')
    
if __name__ == '__main__':
    main()