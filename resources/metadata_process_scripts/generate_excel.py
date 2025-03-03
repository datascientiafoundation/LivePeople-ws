import os, glob, yaml
import pandas as pd
from datetime import datetime
import json
from collections import Counter
import re
from numpy.f2py.crackfortran import expectbegin
import pycountry
import pycountry_convert as pc
import numpy as np
import urllib.request


def validate_and_normalize_date(date_string):
    """
    Validate and normalize date strings to the format YYYY-MM-DD.
    If the date is invalid or incomplete, return the original string.
    """
    try:
        # Parse the date and normalize it to YYYY-MM-DD
        normalized_date = datetime.strptime(date_string, "%Y-%m-%d").strftime("%Y-%m-%d")
        return normalized_date
    except ValueError:
        # If the date is invalid, return the original string
        return date_string


def extract_resources(data):
    extracted = dict()
    tech_report_keywords = ['technical',
                            'descriptor',
                            'Big-Thick Data generation via reference and personal context unification']
    if data['title'] == '2024-SmartUnitn2 OSM Big Thick Data-Trento':
        print('')

    if '2018-SmartUnitnTwo-Trento' in data['title']:
        for res in data['resources']:
            if any(keyword in str(res['name']).lower() for keyword in tech_report_keywords):
                extracted['technical_report'] = res

            elif 'codebook' in str(res['name']).lower() and data['category'] == "Dataset":
                if data['dataset_name'] == 'Questionnaire' and 'codebook(a)' in res['name']:
                    extracted['codebook'] = res
                elif data['dataset_name'] == 'Time Diaries' and 'codebook(b)' in res['name']:
                    extracted['codebook'] = res
                elif data['dataset_type'] == 'Sensor' and 'codebook(c)' in res['name']:  # any sensor
                    extracted['codebook'] = res

            elif 'additional' in str(res['name']).lower():
                extracted['additional_material'] = res

    else:

        for res in data['resources']:
            # check nan and None
            if not res['name'] or str(res['name']).lower() == 'nan':
                continue

            if any(keyword.lower() in str(res['name']).lower() for keyword in tech_report_keywords):
                extracted['technical_report'] = res

            elif 'codebook' in str(res['name']).lower() and data['category'] == "Dataset":
                extracted['codebook'] = res
            elif 'codebook' in str(res['name']).lower() and data['category'] != "Dataset":
                continue
            elif 'html' in str(res['name']).lower():
                extracted['codebook'] = res

            else:
                extracted['additional_material'] = res

    empty_resource = {'name': '', 'url': '', 'format': ''}
    all_keys = ['codebook', 'technical_report', 'additional_material']
    for res in all_keys:
        if res not in extracted.keys():
            extracted[res] = empty_resource

    return extracted


def read_md_files_and_extract_data(md_files_pattern) -> pd.DataFrame:
    # List to store the extracted data
    extracted_data = []

    # Loop through all the markdown files matching the pattern
    files = glob.glob(md_files_pattern)
    for md_file in files:
        with open(md_file, 'r', encoding='utf-8') as file:
            # Read the file contents
            content = file.read()

            # Extract the YAML front matter from the Markdown file
            try:
                # Split the file content to get the YAML block
                yaml_content = content.split('---')[1]  # The second part after `---` is the YAML

                # Parse the YAML content into a dictionary
                data = yaml.safe_load(yaml_content)

                data['category'] = data['category'][0] if len(data['category']) == 1 else data['category']
                # data['file_name'] = os.path.basename(md_file)

                resources = extract_resources(data)

                data['technical_report-name'] = resources['technical_report']['name']
                data['technical_report-url'] = resources['technical_report']['url']
                data['technical_report-format'] = resources['technical_report']['format']
                data['codebook-name'] = resources['codebook']['name']
                data['codebook-url'] = resources['codebook']['url']
                data['codebook-format'] = resources['codebook']['format']
                data['additional_material-name'] = resources['additional_material']['name']
                data['additional_material-url'] = resources['additional_material']['url']
                data['additional_material-format'] = resources['additional_material']['format']

                pattern = r'<a href="([^"]+)">'
                match = re.search(pattern, data['project_url'])
                if match:
                    data['project_url'] = match.group(1)

                if 'other_format' not in data.keys():
                    data['other_format'] = "unknown"
                if str(data['other_format']) in ["nan", "unknown", ""]:
                    data['other_format'] = "unknown"

                # some md have licence  ./././resources/2023LivePeopleLicense.html
                # should be  ./../../resources/2023LivePeopleLicense.html

                if data['license'].startswith('./././'):
                    data['license'] = data['license'].replace('./././', './../../')

                extracted_data.append(data)
            except Exception as e:
                print(f"Error processing file {md_file}: {e}")

    # Convert the extracted data into a pandas DataFrame
    return pd.DataFrame(extracted_data)


def save_to_excel(category_groups, output_file):
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        for category, group in category_groups.items():
            if category == 'Project':
                group = group[[c for c in group.columns if 'ds:prj' in c]]
            if category == 'Dataset' or category == 'Dataset Bundle':
                group = group[[c for c in group.columns if 'ds:Dat' in c]]
            group.to_excel(writer, sheet_name=category, index=False)

    print(f"Data saved to {output_file}")


def create_facet(df) -> pd.DataFrame:
    df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
    df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')

    # Duration Facet
    def categorize_duration(duration):
        months = duration.days // 30  # Convert days to approximate months
        if months < 1:
            return '1 month'
        elif 1 <= months <= 6:
            return '2-6 months'
        elif 7 <= months <= 12:
            return '7-12 months'
        elif months > 12:
            return '>12 months'
        else:
            return 'Unknown'

    df['duration_facet'] = df['end_date'] - df['start_date']
    df['duration_facet'] = df['duration_facet'].apply(categorize_duration)

    # Location Facet
    df['location_facet'] = df['location'].str.extract(r'\((.*?)\)', expand=False)

    def country_to_continent(country_name):
        country_alpha2 = pc.country_name_to_country_alpha2(country_name)
        country_continent_code = pc.country_alpha2_to_continent_code(country_alpha2)
        country_continent_name = pc.convert_continent_code_to_continent_name(country_continent_code)
        return country_continent_name

    df['location_continent_facet'] = df['location_facet'].apply(country_to_continent)

    # Data type facet. sensors have types in sensor_type column, dataset_bundles have values from dataset_name
    df['data_type_facet'] = df['dataset_type']
    df['data_type_facet'] = df.apply(
        lambda row: row['sensor_type'] if row['category'] == 'Dataset' and row['sensor_type'] != None else row[
            'data_type_facet'], axis=1)
    df['data_type_facet'] = df.apply(
        lambda row: row['dataset_name'] if 'Sensors' == row['data_type_facet'] else row['data_type_facet'], axis=1)

    df['data_type_facet'] = df['data_type_facet'].replace('Inertial', 'Position')

    # Projects Diversity1-London, Diversity1-Trento
    # df['project_facet'] = df['title'].str.split('-').str[1] + '-' + df['title'].str.split('-').str[2]

    return df


def get_project_info(df, df_project):
    df['temp_title'] = df.apply(lambda row: row['title'].split('-')[1] + '-' + row['title'].split('-')[2] if row[
                                                                                                                 'category'] == 'Project' else None,
                                axis=1)
    # df = df.merge(df_project[['ds:prjTitle', 'ds:prjStartDate', 'ds:prjEndDate']],
    #               left_on='temp_title',
    #               right_on='ds:prjTitle',
    #               how='left')

    for index, row in df.iterrows():
        matching_row = df_project[df_project['ds:prjTitle'] == row['temp_title']]
        if not matching_row.empty:
            for column in df.columns:
                if column in df_project.columns and str(df.loc[index, column]) == 'nan':
                    df.loc[index, column] = matching_row.iloc[0][column]
    # df = df.merge(df_project,
    #               left_on='temp_title',
    #               right_on='ds:prjTitle',
    #               how='left')

    df.drop(columns=['temp_title'], inplace=True)

    return df


def get_dates(df, df_project):
    df['temp_title'] = df['title'].str.split('-').str[1] + '-' + df['title'].str.split('-').str[2]

    df = df.merge(df_project[['ds:prjTitle', 'ds:prjStartDate', 'ds:prjEndDate']],
                  left_on='temp_title',
                  right_on='ds:prjTitle',
                  how='left')

    df['start_date'] = df.apply(
        lambda row: row['ds:prjStartDate'] if pd.notnull(row['ds:prjStartDate']) else row['start_date'], axis=1)
    df['end_date'] = df.apply(lambda row: row['ds:prjEndDate'] if pd.notnull(row['ds:prjEndDate']) else row['end_date'],
                              axis=1)

    # Drop unnecessary columns if needed
    df = df.drop(columns=['ds:prjTitle'])
    df = df.drop(columns=['ds:prjStartDate'])
    df = df.drop(columns=['ds:prjEndDate'])
    df = df.drop(columns=['temp_title'])

    return df


def fix_title(df):
    # Strip leading/trailing spaces and ensure proper formatting
    df['title'] = df['title'].str.strip()
    k = df.copy()
    # Apply replacements
    replacements_title = {
        'Wenet DiversityOne': 'DiversityOne',
        '2024-SmartUnitnTwo OpenStreetMap Big-thick Data-Trento': '2024-SmartUnitn2OSM-Trento',
        '2024-SmartUnitnTwoOpenStreetMap-Trento-Big Thick Data': '2024-SmartUnitn2OSM-Trento-Time Diaries',

        'Chat Application 1': 'ChatApplication1',
        'Chat Application 2': 'ChatApplication2',
        'Smart Unitn 2': 'SmartUnitn2',

        'Two': '2',
        'One': '1',

        'OC1': 'OpenCalls',
        'OC2': 'OpenCalls',
        'Open Calls': 'OpenCalls',
        'OpenStreetMap': 'OSM',
        'Asuncion': 'Asunción',
        'San Luis Potosi': 'San Luis Potosí',
        'San Luis Potosí ': 'San Luis Potosí',

        'Diversity1': 'DiversityOne',  # only case that should have letter One
        '-Bluetooth Normal': '-Bluetooth',
        '-Bluetooth Low Energy': '-Bluetooth',
        'Doze Mode': 'Doze',
        'Location  Per Time RD': 'Location RD',
        'Location$': 'Location RD',
        'WIFI': 'Wifi',
        'Ringmode': 'Ring Mode',
        'Rotationvector': 'Rotation Vector',
        'Location  POI': 'Location POI',
        'Ulan Bator': 'Ulaanbaatar',
        'Questionnaire-Exit-Survey': 'Questionnaire Exit Survey',
        'Contribution Answers': 'Time Diaries',
        'Contribution Questions': 'Time Diaries',
        'Batterycharge': 'Battery Charge',
        'Questionnaire Diversity A': 'Questionnaire Part 1',
        'Questionnaire Diversity B': 'Questionnaire Part 2',
        'Questionnaire Diversity C': 'Questionnaire Part 3',
        # "r'\bLocation\b'": 'Location RD'
    }

    for old_value, new_value in replacements_title.items():
        df['title'] = df['title'].str.replace(old_value, new_value, regex=True)

    # special case: 2024-SmartUnitn2 OSM Big Thick Data-Trento

    # df.loc[
    #     (df['dataset_name'] == 'Time Diaries') & (df['title'] == '2024-SmartUnitn2 OSM Big Thick Data-Trento'),
    #     'title'
    # ] = '2024-SmartUnitn2 OSM Big Thick Data-Trento-Time Diaries'

    # df['title'] = df['title'].replace({'Bluetooth Low Energy': 'Bluetooth'}, regex=True)

    return df


def fix_collection_name(df):
    # Strip leading/trailing spaces and ensure proper formatting
    df['collection_name'] = df['collection_name'].str.strip()

    # Apply replacements
    replacements = {
        'Diversity1': 'DiversityOne',
        'OC-FPT': 'OpenCalls',
        'OC-UTH': 'OpenCalls',
        'OC2': 'OpenCalls',
        'SKEL': 'Skel',
        'Chatbot1': 'ChatApplication1',
        'Mak': 'Makerere',
        'MAK': 'Makerere',
        'Makerereerere': 'Makerere',
    }

    for old_value, new_value in replacements.items():
        df['collection_name'] = df['collection_name'].str.replace(old_value, new_value, regex=True)

    df['collection_name'] = df.apply(
        lambda row: 'SmartUnitn2OSM' if 'SmartUnitn2OSM' in row['title'] else row['collection_name'], axis=1)

    return df


def fix_dataset_name(df):
    # Apply replacements
    replacements = {
        'Wifinetworks': 'Wifi Networks',
        'WIFI Networks': 'Wifi Networks',
        'WIFI': 'Wifi',
        'Stepdetector': 'Step Detector',
        'Rotationvector': 'Rotation Vector',
        'Ringmode': 'Ring Mode',
        'Location s': 'Location',
        'Location  Per Time RD': 'Location RD',
        'Doze Mode': 'Doze',
        'Diachronic Interactions': 'Diachronic-Interactions',
        'Batterycharge': 'Battery Charge',
        'Device Usage': 'Device-usage',
        'App usage': 'App-usage',
        'Bluetooth Normal': 'Bluetooth',
        'Synchronic Interactions': 'Synchronic-Interactions',
        'Questionnaire Exit Survey': 'Questionnaire',
        'Questionnaire-Exit-Survey': 'Questionnaire',
        'Bluetooth Low Energy': 'Bluetooth',
        'Questionnaire Diversity A': 'Questionnaire Part 1',
        'Questionnaire Diversity B': 'Questionnaire Part 2',
        'Questionnaire Diversity C': 'Questionnaire Part 3',
    }

    for old_value, new_value in replacements.items():
        df['dataset_name'] = df['dataset_name'].str.replace(old_value, new_value, regex=True)
    return df


def fix_license(df):
    df['license'] = df['license'].replace(
        'https://datascientiafoundation.github.io/LivePeople/resources/2023LivePeopleLicense.html',
        './../../resources/2023LivePeopleLicense.html')
    return df


def fix_locations(df):
    replacements = {
        'Asuncion (Paraguay)': 'Asunción (Paraguay)',
        'London (UK)': 'London (United Kingdom)',
        'San Luis Potosi (Mexico)': 'San Luis Potosí (Mexico)',
        'Trento (IT)': 'Trento (Italy)',
        'Ulan Bator (Mongolia)': 'Ulaanbaatar (Mongolia)',
        'Ulan-Bator (Mongolia)': 'Ulaanbaatar (Mongolia)'

    }

    for old_value, new_value in replacements.items():
        df['location'] = df['location'].replace(old_value, new_value)

    return df


def fix_dataset_types(df):
    def process_dataset_type(row):
        if not isinstance(row, str):
            # Handle cases where the row is None or not a string
            return row, None
        if 'Sensors' in row and '<a href' in row:
            # Separate 'Sensors' and links
            sensors_part = 'Sensors'  # Keep only 'Sensors'
            links_part = re.findall(r'<a href="(.*?)">.*?</a>', row)  # Extract links
            return sensors_part, ', '.join(links_part)  # Return both as a tuple
        if '<a href' in row:
            # If only links exist, keep the links and set 'Sensors' column as NaN or empty
            links_part = re.findall(r'<a href="(.*?)">.*?</a>', row)  # Extract links
            return None, ', '.join(links_part)  # Return empty for sensors
        else:
            # If no links and no 'Sensors', keep the dataset_type as is
            return row, None

    # Apply the function to create the two new columns
    df[['dataset_type', 'dataset_type_link']] = df['dataset_type'].apply(
        lambda row: pd.Series(process_dataset_type(row)))

    df['dataset_type'] = df.apply(lambda row: None if 'Project' == row['category'] else row['dataset_type'], axis=1)
    df['dataset_type'] = df.apply(
        lambda row: 'Sensor' if 'Dataset' == row['category'] and row['dataset_type'] == 'Sensors' else row[
            'dataset_type'], axis=1)
    df['dataset_type'] = df.apply(
        lambda row: 'Sensors' if 'Datasets' == row['category'] and row['dataset_type'] == 'Sensor' else row[
            'dataset_type'], axis=1)

    return df


def fix_sensor_types(df):
    # Define a function to process the dataset_type
    def process_dataset_type(row):
        if not isinstance(row, str):
            # Handle cases where the row is None or not a string
            return row, None
        if '<a href=' in row:
            # If only links exist, keep the links and set 'Sensors' column as NaN or empty
            links_part = re.findall(r'<a href="(.*?)">.*?</a>', row)  # Extract links
            return None, ', '.join(links_part)  # Return empty for sensors
        elif '<a href =' in row:
            # If only links exist, keep the links and set 'Sensors' column as NaN or empty
            links_part = re.findall(r'<a href ="(.*?)">.*?</a>', row)  # Extract links
            return None, ', '.join(links_part)  # Return empty for sensors
        else:
            # If no links and no 'Sensors', keep the dataset_type as is
            return row, None

    # Apply the function to create the two new columns

    df[['sensor_type', 'sensor_type_link']] = df['sensor_type'].apply(lambda row: pd.Series(process_dataset_type(row)))

    df['sensor_type'] = df['sensor_type'].apply(
        lambda x: None if x == 'unknown' or str(x) == 'nan' or str(x) == '' else x)
    df['sensor_type'] = df['sensor_type'].replace('App usage', 'App-usage')
    df['sensor_type'] = df['sensor_type'].replace('Device-usage', 'Device-usage')
    df['sensor_type'] = df['sensor_type'].replace('Device usage', 'Device-usage')
    df['sensor_type'] = df['sensor_type'].replace('Device-Usage', 'Device-usage')
    df['sensor_type'] = df['sensor_type'].replace('App-Usage', 'App-usage')
    return df


def fix_note(df):
    # Update 'sensor_details' where 'collection_name' is 'DiversityOne'
    df.loc[df['collection_name'] == 'DiversityOne', 'notes'] = \
        df.loc[df['collection_name'] == 'DiversityOne', 'notes'].str.replace(
            '27 smartphone sensors', '26 smartphone sensors', regex=False
        )

    return df


def get_identifier_dict(path):
    catalog_dict = pd.read_excel(path, sheet_name='WIP_identifier')
    catalog_dict['Collection name'] = catalog_dict['Collection name'].replace(
        {'Diversity1': 'DiversityOne', 'Chatbot1': 'ChatApplication1',
         'Chatbot2': 'ChatApplication2', 'Chatbot3': 'ChatApplication3',
         'Mak': 'Makerere', 'OSM': 'SmartUnitn2OSM'})

    identifier_dict = {
        "Year": {},
        "Collection name": {},
        "Location": {},
        "Dataset name": {},
    }
    try:
        for index, row in catalog_dict.iterrows():
            if not pd.isna(row['Year']):
                identifier_dict['Year'][str(int(row['Year']))] = f'00{int(row["Year identifier"])}'
            if not pd.isna(row['Collection name']):
                identifier_dict['Collection name'][row['Collection name']] = row['Collection identifier']
            if not pd.isna(row['Location']):
                identifier_dict['Location'][row['Location']] = row['Location identifier']
            if not pd.isna(row['New catalog dataset name']) and row['Status'] == 'active':
                identifier_dict['Dataset name'][row['New catalog dataset name']] = row['Dataset identifier']
    except Exception as e:
        print(e)
        print(f'index: {index}')

    return identifier_dict


def fix_identifier(data):
    # identifier correction
    identifier_dict = get_identifier_dict(
        '/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/sources/2024-LivePeople_Metadata_Description-v2.xlsx')

    def check_identifier(row, identifier_dict):

        if row['category'] != 'Dataset':
            return row

        title_splits = row['title'].split('-')

        new_identifier = []

        new_identifier.append(identifier_dict["Year"].get(title_splits[0], 'None'))

        if title_splits[1] == 'OpenCalls' and title_splits[2] == 'Thessaloniki':
            new_identifier.append(identifier_dict["Collection name"].get('WeNetOC-UTH', 'None'))
        elif title_splits[1] == 'OpenCalls' and title_splits[2] == 'Hanoi':
            new_identifier.append(identifier_dict["Collection name"].get('WeNetOC-FTP', 'None'))
        else:
            new_identifier.append(identifier_dict["Collection name"].get(title_splits[1], 'None'))

        new_identifier.append(identifier_dict["Location"].get(title_splits[2], 'None'))
        if len(title_splits) > 3:
            if 'Questionnaire' in title_splits[3]:
                new_identifier.append(identifier_dict["Dataset name"].get('Questionnaire', 'None'))
            else:
                new_identifier.append(identifier_dict["Dataset name"].get(title_splits[3], 'None'))

        # id_part = splits[4] if len(splits) > 4 else None

        new_identifier = '.'.join(new_identifier)
        if new_identifier != row['identifier']:
            print(f"no match identifier on title: {row['title']}, on {new_identifier} != {row['identifier']}")

        row['identifier'] = new_identifier

        return row

    data = data.apply(check_identifier, identifier_dict=identifier_dict, axis=1)

    # Solve duplicated
    dataset_df = data[data['category'] == 'Dataset']
    identifier_counts = dataset_df.identifier.value_counts()
    filtered_data = dataset_df[dataset_df['identifier'].isin(identifier_counts[identifier_counts > 1].index)][
        ['title', 'category', 'identifier']]
    filtered_data['identifier_old'] = filtered_data['identifier']

    # Create a mapping for category to number
    category_map = {'1': 1, '2': 2, '3': 3}

    # Iterate over each group of rows with the same identifier
    for identifier, group in filtered_data.groupby('identifier'):
        # Iterate over the rows in the group
        for idx, row in group.iterrows():
            # Extract the letter at the end of the title (A, B, C)
            title_ending = row['title'][-1]

            # If the title ends with A, B, or C, update the identifier accordingly
            if title_ending in category_map:
                new_identifier = row['identifier'] + '.' + str(category_map[title_ending])
                filtered_data.at[idx, 'identifier'] = new_identifier

    data['identifier'] = data.apply(
        lambda row: filtered_data.loc[filtered_data['title'] == row['title'], 'identifier'].values[0]
        if row['title'] in filtered_data['title'].values else row['identifier'], axis=1)

    # TODO one for dataset bundles

    def gen_bundle_identifier(row, dataset_df):
        if row['category'] != 'Dataset Bundle':
            return row

        year_collection_city = '-'.join(row['title'].split('-')[0:3])
        bundle_name = '-'.join(row['title'].split('-')[3:])

        if bundle_name == 'Diachronic-Interactions' or bundle_name == 'Synchronic-Interactions':
            filtered = dataset_df[(dataset_df['title'].str.startswith(year_collection_city)) & (
                    dataset_df['dataset_type'] == bundle_name)]
        elif bundle_name == 'Daily annotations & Location RD':
            filtered = dataset_df[dataset_df['title'].isin(
                [f'{year_collection_city}-Location RD', f'{year_collection_city}-Time Diaries'])]

        else:
            filtered = dataset_df[(dataset_df['title'].str.startswith(year_collection_city)) & (
                    dataset_df['sensor_type'] == bundle_name)]
        idfs = filtered.sort_values(by='title')['identifier'].tolist()

        try:
            new_identifier = [idfs[0]]  # must
            for idf in idfs[1:]:
                new_identifier.append('.'.join(idf.split('.')[3:]))

            row['identifier'] = '-'.join(new_identifier)
        except Exception as e:
            print(f'Error {e}, on {row["title"]}')

        print(f"{row['title']} - {row['identifier']}")
        return row

    data = data.apply(gen_bundle_identifier, args=(data[data['category'] == 'Dataset'],), axis=1)

    # TODO one for projects
    def gen_project_identifier(row, dataset_df):
        if row['category'] != 'Project':
            return row
        try:
            first_match = dataset_df[dataset_df['title'].str.startswith(row['title'])].iloc[0]
            row['identifier'] = '.'.join(first_match['identifier'].split('.')[0:3]) + "." + "**"
        except Exception as e:
            print(f'Error {e}, on {row["title"]}')
        return row

    data = data.apply(gen_project_identifier, args=(data[data['category'] == 'Dataset'],), axis=1)

    return data


def fix_file_name(df):
    df['file_name'] = df['title'] + '.md'
    return df


def merge_row(df):
    merge_groups = [
        {'2022-OC1-Hanoi-Contribution Answers', '2022-OC1-Hanoi-Contribution Questions'},
        {'2022-OC2-Thessaloniki-Contribution Answers', '2022-OC2-Thessaloniki-Contribution Questions'},
        {'2021-ChatApplicationTwo-Trento-Bluetooth Low Energy', '2021-ChatApplicationTwo-Trento-Bluetooth Normal'},
        {'2022-OC1-Hanoi-Bluetooth Low Energy', '2022-OC1-Hanoi-Bluetooth Normal'},
        {'2022-OC2-Thessaloniki-Bluetooth Low Energy', '2022-OC2-Thessaloniki-Bluetooth Normal'}
    ]

    # Iterate through each group of titles to merge
    for titles_to_merge in merge_groups:
        # Find the matching rows
        rows_to_merge = df[df['title'].isin(titles_to_merge)]

        if not rows_to_merge.empty:
            # Create a new row (copy one row's data)
            new_row = rows_to_merge.iloc[0].copy()

            # Sum the 'size' column
            new_row['size'] = float(rows_to_merge['size'].iloc[0].split(' ')[0]) + float(
                rows_to_merge['size'].iloc[1].split(' ')[0])

            # Remove the original rows from the DataFrame
            df = df[~df['title'].isin(titles_to_merge)]

            # Append the new merged row
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    return df


def normalize_values(df):
    # remove dup
    df = merge_row(df)

    df = fix_title(df)

    df = fix_license(df)

    df = fix_locations(df)

    df = fix_collection_name(df)

    df = fix_dataset_name(df)

    # separates links from dataset_type column to dataset_type_link
    df = fix_dataset_types(df)

    # separates links from sensor_type column to sensor_type_link
    df = fix_sensor_types(df)

    # file name - should be at the end cuz it is taken from title
    # df = fix_file_name(df)

    # note - custom
    df = fix_note(df)

    df = fix_identifier(df)

    return df


def get_missing_codebooks(df):
    # CHAT APP 2
    sensors = {
        "Chat_data.html": "2021-ChatApplication2-Chat_data.html",
        "applicationevent.html": "2021-ChatApplication2-applicationevent.html",
        "notificationevent.html": "2021-ChatApplication2-notificationevent.html",
        "Exit_survey.html": "2021-ChatApplication2-Exit_survey.html",
        "bluetoothlowenergyevent.html": "2021-ChatApplication2-bluetoothlowenergyevent.html",
        "stepcounterevent.html": "2021-ChatApplication2-stepcounterevent.html",
        "Profile": "2021-ChatApplication2-Profile.html",
        "bluetoothnormalevent.html": "2021-ChatApplication2-bluetoothnormalevent.html",
        "stepdetectorevent.html": "2021-ChatApplication2-stepdetectorevent.html",
        "Activities Per Label": "2021-ChatApplication2-activitiesperlabel.html",
        "locationeventpertime_poi.html": "2021-ChatApplication2-locationeventpertime_poi.html",
        "activitiespertime.html": "2021-ChatApplication2-activitiespertime.html",
        "locationeventpertime_rd.html": "2021-ChatApplication2-locationeventpertime_rd.html"
    }

    base_url = 'https://datascientiafoundation.github.io/LivePeople-Documentation'
    def generate_codebook_url(row):

        if row['codebook-url'].startswith('https://drive.google.com') and row['collection_name'] != 'SmartUnitn2':
            return base_url + '/2021-ChatApplication2/' + sensors.get(row['codebook-name'], 'default.html')
        return row['codebook-url']

    df['codebook-url'] = df.apply(generate_codebook_url, axis=1)

    def update_codebook_url(row):
        if row['title'] == '2020-DiversityOne-San Luis Potosí-Gyroscope':
            row['codebook-url'] = base_url + '/codebooks/2020_DV1_San-Luis-Potosi_gyroscope.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'


        if row['title'] == '2020-DiversityOne-Amrita-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Amrita_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Amrita-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Amrita_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Amrita-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Amrita_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Amrita-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Amrita_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'


        if row['title'] == '2020-DiversityOne-Asunción-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Asuncion_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Asunción-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Asuncion_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Asunción-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Asuncion_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Asunción-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Asuncion_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'


        if row['title'] == '2020-DiversityOne-Copenhagen-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Copenhagen_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Copenhagen-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Copenhagen_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Copenhagen-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Copenhagen_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Copenhagen-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Copenhagen_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'


        if row['title'] == '2020-DiversityOne-Jilin-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Jilin_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Jilin-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Jilin_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Jilin-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Jilin_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Jilin-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Jilin_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'



        if row['title'] == '2020-DiversityOne-London-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_London_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-London-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_London_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-London-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_London_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-London-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_London_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'



        if row['title'] == '2020-DiversityOne-San Luis Potosí-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_San-Luis-Potosi_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-San Luis Potosí-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_San-Luis-Potosi_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-San Luis Potosí-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_San-Luis-Potosi_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-San Luis Potosí-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_San-Luis-Potosi_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'



        if row['title'] == '2020-DiversityOne-Trento-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Trento_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Trento-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Trento_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Trento-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Trento_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Trento-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Trento_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'



        if row['title'] == '2020-DiversityOne-Ulaanbaatar-Questionnaire Part 1':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Ulan-Bator_survey1.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Ulaanbaatar-Questionnaire Part 2':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Ulan-Bator_survey2.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Ulaanbaatar-Questionnaire Part 3':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Ulan-Bator_survey3.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'
        if row['title'] == '2020-DiversityOne-Ulaanbaatar-Time Diaries':
            row['codebook-url'] = base_url + '/codebooks/' + '2020_DV1_Ulan_Bator_timediaries.html'
            row['codebook-name'] = 'Codebook'
            row['codebook-format'] = 'html'

        return row

    df = df.apply(update_codebook_url, axis=1)




    return df


def read_project(path):
    df_project = pd.read_excel(path)

    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('WeNet-', '', regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('Diversity1', 'DiversityOne', regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('SmartUnitn', 'SmartUnitn2', regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('Big-Thick Data Project', 'SmartUnitn2OSM-Trento',
                                                                      regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('_', '-', regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('Tessaloniki', 'Thessaloniki', regex=False)
    df_project['ds:prjTitle'] = df_project['ds:prjTitle'].str.replace('Ulan Bator', 'Ulaanbaatar', regex=False)
    df_project.rename(columns={'ds:prjOverallPeopleInvolved': 'ds:prjOverallParticipantsInvolved'}, inplace=True)

    return df_project


def mapping_to_md_column_names(df):
    import modeling as md

    project_columns = md.project.keys()
    dataset_columns = md.dataset.keys()

    project_mapping = {
        key: value for key, value in md.project.items()
        if value and value != ''
    }

    dataset_mapping = {
        key: value for key, value in md.dataset.items()
        if value and value != ''
    }

    df = pd.concat([df, pd.DataFrame(None, index=df.index, columns=project_columns)], axis=1)
    df = pd.concat([df, pd.DataFrame(None, index=df.index, columns=dataset_columns)], axis=1)

    for key, value in project_mapping.items():
        df[key] = df[value]

    for key, value in dataset_mapping.items():
        df[key] = df[value]

    return df


def is_valid_url(url, col):
    if not url:  # Handle empty values (None, '', etc.)
        return ''
    try:
        response = urllib.request.urlopen(url)
        return url  # Keep the URL if it's valid
    except Exception as e:
        print(f"--- URL error - excluded from catalog: {getattr(e, 'code', 'NoCode')} | Column: {col} | URL: {url}")
        return ''  # Return empty to indicate removal


def main(md_files_pattern, project_file, metadata_description, output_file):
    # Extract data from the markdown files
    data = read_md_files_and_extract_data(md_files_pattern)
    df_project = read_project(project_file)
    df_md_description = pd.read_excel(metadata_description, sheet_name=None)

    # clean inconsistent values
    data = normalize_values(data)

    data = get_dates(data, df_project)

    data = get_missing_codebooks(data)

    # Creating FACET
    data = create_facet(data)

    # add column names from metadata description
    data = mapping_to_md_column_names(data)

    data = get_project_info(data, df_project)

    # custom
    data['ds:DatDownloadRequestName'] = 'Download request'
    data[
        'ds:DatDownloadRequestURL'] = 'https://datascientiafoundation.github.io/LivePeople/resources/download_request.pdf'
    data['ds:DatDownloadRequestFormat'] = 'PDF'

    data['ds:prjIsVisible'] = True
    data['ds:DatIsVisible'] = True

    data['ds:prjIsVisible'] = data['ds:prjTitle'].apply(lambda x: False if '2023-Skel-Trento' in x else True)
    data['ds:DatIsVisible'] = data['ds:DatName'].apply(lambda x: False if '2023-Skel-Trento' in x else True)

    data['ds:prjWebpage'] = data.apply(lambda x: 'https://datascientia.disi.unitn.it/projects/su2/' if x[
                                                                                                           'ds:prjTitle'] == '2018-SmartUnitn2-Trento' else
    x['ds:prjWebpage'], axis=1)
    data['ds:prjWebpage'] = data.apply(
        lambda x: 'https://datascientia.disi.unitn.it/projects/diversityone/' if 'DiversityOne' in x['ds:prjTitle'] else
        x['ds:prjWebpage'], axis=1)
    data['ds:prjWebpage'] = data.apply(lambda x: '' if 'ChatApplication' in x['ds:prjTitle'] else x['ds:prjWebpage'],
                                       axis=1)
    data['ds:prjWebpage'] = data.apply(lambda x: '' if 'OpenCalls' in x['ds:prjTitle'] else x['ds:prjWebpage'], axis=1)

    # skel dont have project url for trento
    data['ds:prjWebpage'] = data.apply(lambda
                                           x: 'https://ds.datascientia.eu/community/public/projects/2f39ee2e-4012-4fa8-9794-a56bce243d3e' if 'Skel' in
                                                                                                                                             x[
                                                                                                                                                 'ds:prjTitle'] else
    x['ds:prjWebpage'], axis=1)
    data['ds:prjURL'] = data.apply(lambda
                                       x: 'https://ds.datascientia.eu/community/public/projects/2f39ee2e-4012-4fa8-9794-a56bce243d3e' if 'Skel' in
                                                                                                                                         x[
                                                                                                                                             'ds:prjTitle'] else
    x['ds:prjURL'], axis=1)

    data['ds:prjURL'] = data.apply(lambda
                                       x: 'https://ds.datascientia.eu/community/public/projects/8b227ff7-803e-4f7b-8765-75ea2b7a8113' if 'SmartUnitn2OSM' in
                                                                                                                                         x[
                                                                                                                                             'ds:prjTitle'] else
    x['ds:prjURL'], axis=1)

    data['ds:prjAdditionalMaterialName'] = data.apply(
        lambda row: 'Dataset paper and data collection methodology' if 'DiversityOne' in row[
            'ds:prjCollectionFacet'] else row['ds:prjAdditionalMaterialName'], axis=1)
    data['ds:prjAdditionalMaterialURL'] = data.apply(
        lambda row: 'https://arxiv.org/abs/2502.03347' if 'DiversityOne' in row['ds:prjCollectionFacet'] else row[
            'ds:prjAdditionalMaterialURL'], axis=1)
    data['ds:prjAdditionalMaterialFormat'] = data.apply(
        lambda row: 'PDF' if 'DiversityOne' in row['ds:prjCollectionFacet'] else row['ds:prjAdditionalMaterialFormat'],
        axis=1)

    data.loc[data['ds:DatCodebookName'].notna() & (data['ds:DatCodebookName'] != ''), 'ds:DatCodebookName'] = 'Codebook'

    data['ds:prjDocumentationName'] = data.apply(
        lambda row: 'Dataset technical report' if pd.notna(row['ds:prjDocumentationName']) and row[
            'ds:prjDocumentationName'] != '' else row['ds:prjDocumentationName'], axis=1)

    data.loc[data[
                 'ds:prjCollectionFacet'] == 'DiversityOne', 'ds:prjCiteAs'] = 'Matteo Busso, Andrea Bontempelli, Leonardo Javier Malcotti, Lakmal Meegahapola, Peter Kun, Shyam Diwakar, Chaitanya Nutakki, Marcelo Rodas Britez,Hao Xu, Donglei Song, Salvador Ruiz-Correa, Andrea-Rebeca Mendoza-Lara, George Gaskell, Sally Stares, Miriam Bidoglia, Amarsanaa Ganbold, Altangerel Chagnaa, Luca Cernuzzi, Alethia Hume, Ronald Chenu-Abente, Roy Alia Asiku, Ivan Kayongo, Daniel Gatica-Perez, Amalia De Götzen, Ivano Bison, and Fausto Giunchiglia. (2025). DiversityOne: A Multi-Country Smartphone Sensor Dataset for Everyday Life Behavior Modeling. Proceedings of the ACM on interactive, mobile, wearable and ubiquitous technologies.'

    data.loc[data['ds:DatName'].str.endswith('Part 1',
                                             ''), 'ds:DatAdditionalMaterialName'] = 'Additional_material-questionnaire'
    data.loc[data['ds:DatName'].str.endswith('Part 1',
                                             ''), 'ds:DatAdditionalMaterialURL'] = 'https://drive.google.com/file/d/1fXlb2vJfp_HOs4XP_3jaLYM7rTipGygO/view?usp=drive_link'
    data.loc[data['ds:DatName'].str.endswith('Part 1', ''), 'ds:DatAdditionalMaterialFormat'] = 'PDF'

    data.loc[data['ds:DatName'].str.endswith('Part 2',
                                             ''), 'ds:DatAdditionalMaterialName'] = 'Additional_material-questionnaire'
    data.loc[data['ds:DatName'].str.endswith('Part 2',
                                             ''), 'ds:DatAdditionalMaterialURL'] = 'https://drive.google.com/file/d/1jhkBFcruJil2f09xV1dYpjgQL-yqcbaj/view?usp=drive_link'
    data.loc[data['ds:DatName'].str.endswith('Part 2', ''), 'ds:DatAdditionalMaterialFormat'] = 'PDF'

    data.loc[data['ds:DatName'].str.endswith('Part 3',
                                             ''), 'ds:DatAdditionalMaterialName'] = 'Additional_material-questionnaire'
    data.loc[data['ds:DatName'].str.endswith('Part 3',
                                             ''), 'ds:DatAdditionalMaterialURL'] = 'https://drive.google.com/file/d/1bOYnYNkhHjpRO1WW0e2yDCSrKd4KwA-s/view?usp=drive_link'
    data.loc[data['ds:DatName'].str.endswith('Part 3', ''), 'ds:DatAdditionalMaterialFormat'] = 'PDF'

    # Save the extracted data to an Excel file

    data = data.sort_values('title')

    data.drop(columns=['location_continent_facet', 'resources', 'other_format'], inplace=True)
    category_groups = {category: group for category, group in data.groupby('category')}

    filtered_groups = {
        'Project': category_groups['Project'][[c for c in data.columns if 'ds:prj' in c]],
        'Dataset': category_groups['Dataset'][[c for c in data.columns if 'ds:Dat' in c]],
        'Dataset Bundle': category_groups['Dataset Bundle'][[c for c in data.columns if 'ds:Dat' in c]]
    }

    for category, value_df in filtered_groups.items():
        if category == 'Project':
            columns = ['ds:prjURL', 'ds:prjWebpage', 'ds:prjAdditionalMaterialURL', 'ds:prjDocumentationURL']
        else:
            columns = ['ds:DatCodebookURL', 'ds:DatAdditionalMaterialURL', 'ds:DatChangelogURL']

        invalid = set()
        for col in columns:
            uniq_values = value_df[col].dropna().unique()
            for value in uniq_values:
                if value.startswith('https://drive.google.com'):
                    continue
                if value == '':
                    continue
                if is_valid_url(value, col) == '':
                    invalid.add(value)

        # Apply changes directly to the original DataFrame
        if len(invalid) > 0:
            for col in columns:
                if col in ['ds:prjAdditionalMaterialURL', 'ds:prjDocumentationURL', 'ds:DatCodebookURL',
                           'ds:DatAdditionalMaterialURL']:
                    col_name = col.replace('URL', 'Name')
                    col_format = col.replace('URL', 'Format')

                    filtered_groups[category].loc[filtered_groups[category][col].isin(invalid), col_name] = ''
                    filtered_groups[category].loc[filtered_groups[category][col].isin(invalid), col_format] = ''
                filtered_groups[category].loc[filtered_groups[category][col].isin(invalid), col] = ''

    save_to_excel(filtered_groups, output_file)


if __name__ == "__main__":
    # Folder containing the Markdown files
    # md_files_pattern = "/Users/munkhdelger/Knowdive/LivePeople/_datasets/*.md"
    md_files_pattern = "/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/md_old/*.md"

    # Output CSV file
    output_file = "/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/sources/catalog.xlsx"

    project_file = "/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/sources/2024_LivePeople PROJECT Metadata.xlsx"

    metadata_description = '/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/sources/2024_LivePeople PROJECT Metadata.xlsx'

    main(md_files_pattern, project_file, metadata_description, output_file)
