import pandas as pd
import os
import glob
import yaml
from dateutil import parser
import ast
import urllib.parse
import modeling as md


def convert_datetime_formats(date_value):
    if pd.isna(date_value) or date_value == '':
        return ''

    # Parse date
    if isinstance(date_value, str):
        date_value = parser.parse(date_value)

    # Standardize date to "%Y-%m-%d %H:%M:%S"
    standardized_date = date_value.strftime("%Y-%m-%d %H:%M:%S")

    # Check if time is 00:00:00, remove the time if it's exactly at midnight
    if standardized_date.endswith(" 00:00:00"):
        standardized_date = standardized_date.split(" ")[0]

    return standardized_date


def encode_url(title):
    return urllib.parse.quote(title)


def create_href(title):
    base_url = "https://datascientiafoundation.github.io/LivePeople/datasets/"
    link = base_url + encode_url(title)
    return f'<a href="{link}" target="_blank">{title}</a>'


def generate_html_href(category, row, all_df):
    base_url = "https://datascientiafoundation.github.io/LivePeople/datasets/"
    generated_href = []

    # TODO should get component datasets using identifier field
    if category == 'Project':  # Should contain Dataset Bundles

        # get component bundles
        bundle_df = all_df['Dataset Bundle']
        titles = bundle_df[bundle_df['ds:DatName'].str.startswith(row['ds:prjTitle'])]['ds:DatName']

        for title in titles:
            href = create_href(title)
            link = base_url + encode_url(title)
            label = '-'.join(title.split('-')[3:]).capitalize()
            generated_href.append(f'<a href="{link}" target="_blank">{label}</a>')

    elif category == 'Dataset Bundle':

        if row['ds:DatName'] == '2022-OpenCalls-Hanoi-Diachronic-Interactions':
            print()

        year_collection_city = '-'.join(row['ds:DatName'].split('-')[0:3])
        bundle_name = '-'.join(row['ds:DatName'].split('-')[3:])

        dataset_df = all_df['Dataset']

        if bundle_name == 'Daily annotations & Location RD':
            titles = dataset_df[dataset_df['ds:DatName'].isin(
                [f'{year_collection_city}-Location RD', f'{year_collection_city}-Time Diaries'])][
                'ds:DatName']

        elif bundle_name in ['Diachronic-Interactions', 'Synchronic-Interactions']:
            titles = dataset_df[(dataset_df['ds:DatName'].str.startswith(year_collection_city)) & (
                    dataset_df['ds:DatType'] == bundle_name)]['ds:DatName']

        else:
            titles = dataset_df[(dataset_df['ds:DatName'].str.startswith(year_collection_city)) & (
                        dataset_df['ds:DatSensorType'] == bundle_name)][
                'ds:DatName']

        for title in titles:
            link = base_url + encode_url(title)
            label = '-'.join(title.split('-')[3:]).capitalize()
            generated_href.append(f'<a href="{link}" target="_blank">{label}</a>')

    return ', '.join(generated_href)


def create_project_md(df, all_df):
    cnt = 0
    df = df.fillna('')
    df['ds:prjOverallParticipantsInvolved'] = pd.to_numeric(df['ds:prjOverallParticipantsInvolved'],
                                                            errors='coerce').fillna(0).astype(int)
    df['ds:prjSelectedParticipants'] = pd.to_numeric(df['ds:prjSelectedParticipants'],
                                                     errors='coerce').fillna(0).astype(int)
    for index, row in df.iterrows():
        try:
            if not row['ds:prjIsVisible']:
                continue

            file_name = row['ds:prjTitle'] + '.md'
            for key in ["ds:prjStartDate", "ds:prjEndDate", "ds:prjIRBApprovalDate"]:
                row[key] = convert_datetime_formats(row[key])

            md_content = "---\n"
            md_content = md_content + "schema: default" + "\n"
            md_content = md_content + "title: " + row['ds:prjTitle'] + "\n"
            md_content = md_content + "ds:prjURL: <a href=\"" + str(
                row['ds:prjURL']) + "\" target=\"_blank\"> View </a>\n"
            if str(row['ds:prjWebpage']) != '':
                md_content = md_content + "ds:prjWebpage: <a href=\"" + str(
                    row['ds:prjWebpage']) + "\" target=\"_blank\"> View </a>\n"
            md_content = md_content + "ds:prjKeywords: " + str(row['ds:prjKeywords']) + "\n"
            md_content = md_content + "ds:prjType: " + str(row['ds:prjType']) + "\n"
            md_content = md_content + "notes: " + str(row['ds:prjDescription']) + "\n"
            md_content = md_content + f'ds:prjStartDate: "{str(row["ds:prjStartDate"])}"\n'
            md_content = md_content + f'ds:prjEndDate: "{str(row["ds:prjEndDate"])}"\n'
            md_content = md_content + "ds:prjFundingAgency: " + str(row['ds:prjFundingAgency']) + "\n"
            md_content = md_content + "ds:prjInput: " + str(row['ds:prjInput']) + "\n"
            md_content = md_content + "ds:prjOutput: " + str(row['ds:prjOutput']) + "\n"
            md_content = md_content + "ds:prjCoordinator: " + str(row['ds:prjCoordinator']) + "\n"
            md_content = md_content + "ds:prjObservations: " + str(row['ds:prjObservations']) + "\n"
            md_content = md_content + "organization: " + str(row['ds:prjCoordinatorOrganization']) + "\n"
            md_content = md_content + "ds:prjProjectArea: " + str(row['ds:prjProjectArea']) + "\n"
            md_content = md_content + "ds:prjMembers: " + str(row['ds:prjMembers']) + "\n"
            md_content = md_content + "ds:prjTargetLocation: " + str(row['ds:prjTargetLocation']) + "\n"
            md_content = md_content + "ds:prjTargetPopulation: " + str(row['ds:prjTargetPopulation']) + "\n"
            md_content = md_content + "ds:prjOverallParticipantsInvolved: " + str(
                row['ds:prjOverallParticipantsInvolved']) + "\n"
            md_content = md_content + "ds:prjSelectedParticipants: " + str(row['ds:prjSelectedParticipants']) + "\n"
            md_content = md_content + "ds:prjTypeOfMeasurements: " + str(row['ds:prjTypeOfMeasurements']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalDate: " + str(row['ds:prjIRBApprovalDate']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalOrganization: " + str(
                row['ds:prjIRBApprovalOrganization']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalNumber: " + str(row['ds:prjIRBApprovalNumber']) + "\n"
            md_content = md_content + f'ds:prjCiteAs: "{str(row["ds:prjCiteAs"])}"\n'
            md_content = md_content + "ds:prjMaintenance: " + str(row['ds:prjMaintenance']) + "\n"
            md_content = md_content + "latitude_map: " + str(row['ds:prjLatitude']) + "\n"
            md_content = md_content + "longitude_map: " + str(row['ds:prjLongitude']) + "\n"
            md_content = md_content + "ds:prjThumbnailURL: " + str(row['ds:prjThumbnailURL']) + "\n"
            md_content = md_content + "ds:prjIdentifier: " + str(row['ds:prjIdentifier']) + "\n"
            md_content = md_content + "ds:prjDownloadRequestEmail: " + str(row['ds:prjDownloadRequestEmail']) + "\n"

            md_content = md_content + "resources:\n"

            if str(row['ds:prjDocumentationName']) != "nan":
                md_content = md_content + "  - name: " + str(row['ds:prjDocumentationName']) + "\n"
                md_content = md_content + "    url: " + str(row['ds:prjDocumentationURL']) + "\n"
                md_content = md_content + "    format: " + str(row['ds:prjDocumentationFormat']) + "\n"

            if str(row['ds:prjAdditionalMaterialName']) != "nan":
                md_content = md_content + "  - name: " + str(row['ds:prjAdditionalMaterialName']) + "\n"
                md_content = md_content + "    url: " + str(row['ds:prjAdditionalMaterialURL']) + "\n"
                md_content = md_content + "    format: " + str(row['ds:prjAdditionalMaterialFormat']) + "\n"

            # NOTE facet needs to have common field name due to filtering
            md_content = md_content + "duration_facet: " + f'"{str(row["ds:prjDurationFacet"])}"' + "\n"
            md_content = md_content + "location_facet: " + str(row['ds:prjLocationFacet']) + "\n"
            md_content = md_content + "collection_name: " + str(row['ds:prjCollectionFacet']) + "\n"
            md_content = md_content + "category: " + str(row['ds:prjCategoryFacet']) + "\n"

            # for viz
            md_content = md_content + "component_dataset_link: " + generate_html_href('Project', row, all_df) + "\n"

            md_content = md_content + "---\n"

            output_file_path = os.path.join(output_dir, file_name)

            with open(output_file_path, 'w', encoding='utf-8') as md_file:
                md_file.write(md_content)
            cnt = cnt + 1
        except Exception as e:
            print(f"Error: {e}")
    print(f'total proj generated: {cnt}')


def create_dataset_md(df, all_df):
    # df = df.fillna('')
    cnt = 0
    skipped = 0
    for index, row in df.iterrows():
        try:
            if not row['ds:DatIsVisible']:
                print(f"skipped md title: {row['ds:DatName']}")
                skipped = skipped + 1
                continue

            file_name = row['ds:DatName'] + '.md'

            for key in ["ds:DatPublicationTimestamp", "ds:DatExpires", "ds:DatStartDate", "ds:DatEndDate",
                        "ds:DatUpdateTimestamp"]:
                row[key] = convert_datetime_formats(row[key])

            project_title = '-'.join(row['ds:DatName'].split('-')[0:3])
            project_df = all_df['Project']

            project_df['ds:prjOverallParticipantsInvolved'] = pd.to_numeric(
                project_df['ds:prjOverallParticipantsInvolved'],
                errors='coerce').fillna(0).astype(int)
            project_df['ds:prjSelectedParticipants'] = pd.to_numeric(project_df['ds:prjSelectedParticipants'],
                                                                     errors='coerce').fillna(0).astype(int)

            filtered_df = project_df[project_df['ds:prjTitle'] == project_title]
            if filtered_df.empty:
                print(f"No project named: {project_title}")
                project_row = pd.Series({col: float('nan') for col in
                                         project_df.columns})  # for the code to run with empty project row values
            else:
                project_row = filtered_df.iloc[0]

            project_row = project_row.fillna('')
            row = row.fillna('')

            for key in ["ds:prjStartDate", "ds:prjEndDate", "ds:prjIRBApprovalDate"]:
                project_row[key] = convert_datetime_formats(project_row[key])

            md_content = "---\n"

            md_content = md_content + "schema: default" + "\n"
            md_content = md_content + "ds:prjTitle: " + create_href(project_row['ds:prjTitle']) + "\n"  # --> for viz
            md_content = md_content + "ds:prjURL: <a href=\"" + str(
                project_row['ds:prjURL']) + "\" target=\"_blank\"> View </a>\n"
            if str(project_row['ds:prjWebpage']) != '':
                md_content = md_content + "ds:prjWebpage: <a href=\"" + str(
                    project_row['ds:prjWebpage']) + "\" target=\"_blank\"> View </a>\n"
            md_content = md_content + "ds:prjKeywords: " + str(project_row['ds:prjKeywords']) + "\n"
            md_content = md_content + "ds:prjType: " + str(project_row['ds:prjType']) + "\n"
            # md_content = md_content + "notes: " + str(project_row['ds:prjDescription']) + "\n"
            md_content = md_content + f'ds:prjStartDate: "{str(project_row["ds:prjStartDate"])}"\n'
            md_content = md_content + f'ds:prjEndDate: "{str(project_row["ds:prjEndDate"])}"\n'
            md_content = md_content + "ds:prjFundingAgency: " + str(project_row['ds:prjFundingAgency']) + "\n"
            md_content = md_content + "ds:prjInput: " + str(project_row['ds:prjInput']) + "\n"
            md_content = md_content + "ds:prjOutput: " + str(project_row['ds:prjOutput']) + "\n"
            md_content = md_content + "ds:prjCoordinator: " + str(project_row['ds:prjCoordinator']) + "\n"
            md_content = md_content + "ds:prjObservations: " + str(project_row['ds:prjObservations']) + "\n"
            md_content = md_content + "organization: " + str(project_row['ds:prjCoordinatorOrganization']) + "\n"
            md_content = md_content + "ds:prjProjectArea: " + str(project_row['ds:prjProjectArea']) + "\n"
            md_content = md_content + "ds:prjMembers: " + str(project_row['ds:prjMembers']) + "\n"
            md_content = md_content + "ds:prjTargetLocation: " + str(project_row['ds:prjTargetLocation']) + "\n"
            md_content = md_content + "ds:prjTargetPopulation: " + str(project_row['ds:prjTargetPopulation']) + "\n"
            md_content = md_content + "ds:prjOverallParticipantsInvolved: " + str(
                project_row['ds:prjOverallParticipantsInvolved']) + "\n"
            md_content = md_content + "ds:prjSelectedParticipants: " + str(
                project_row['ds:prjSelectedParticipants']) + "\n"
            md_content = md_content + "ds:prjTypeOfMeasurements: " + str(project_row['ds:prjTypeOfMeasurements']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalDate: " + str(project_row['ds:prjIRBApprovalDate']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalOrganization: " + str(
                project_row['ds:prjIRBApprovalOrganization']) + "\n"
            md_content = md_content + "ds:prjIRBApprovalNumber: " + str(project_row['ds:prjIRBApprovalNumber']) + "\n"
            md_content = md_content + f'ds:prjCiteAs: "{str(project_row["ds:prjCiteAs"])}"\n'
            md_content = md_content + "ds:prjMaintenance: " + str(project_row['ds:prjMaintenance']) + "\n"
            md_content = md_content + "latitude_map: " + str(project_row['ds:prjLatitude']) + "\n"
            md_content = md_content + "longitude_map: " + str(project_row['ds:prjLongitude']) + "\n"
            md_content = md_content + "ds:prjThumbnailURL: " + str(project_row['ds:prjThumbnailURL']) + "\n"
            md_content = md_content + "ds:prjIdentifier: " + str(project_row['ds:prjIdentifier']) + "\n"
            md_content = md_content + "ds:prjDownloadRequestEmail: " + str(
                project_row['ds:prjDownloadRequestEmail']) + "\n"

            md_content = md_content + "resources:\n"

            if str(project_row['ds:prjCollectionFacet']) == 'DiversityOne':
                if str(project_row['ds:prjAdditionalMaterialName']) != "nan":
                    md_content = md_content + "  - name: " + str(project_row['ds:prjAdditionalMaterialName']) + "\n"
                    md_content = md_content + "    url: " + str(project_row['ds:prjAdditionalMaterialURL']) + "\n"
                    md_content = md_content + "    format: " + str(project_row['ds:prjAdditionalMaterialFormat']) + "\n"
                # if str(project_row['ds:prjDocumentationName']) != "nan":
                #     md_content = md_content + "  - name: " + str(project_row['ds:prjDocumentationName']) + "\n"
                #     md_content = md_content + "    url: " + str(project_row['ds:prjDocumentationURL']) + "\n"
                #     md_content = md_content + "    format: " + str(project_row['ds:prjDocumentationFormat']) + "\n"
                if str(row['ds:DatCodebookName']) != "nan":
                    md_content = md_content + "  - name: " + str(row['ds:DatCodebookName']) + "\n"
                    md_content = md_content + "    url: " + str(row['ds:DatCodebookURL']) + "\n"
                    md_content = md_content + "    format: " + str(row['ds:DatCodebookFormat']) + "\n"

                if str(row['ds:DatAdditionalMaterialName']) != "nan":
                    md_content = md_content + "  - name: " + str(row['ds:DatAdditionalMaterialName']) + "\n"
                    md_content = md_content + "    url: " + str(row['ds:DatAdditionalMaterialURL']) + "\n"
                    md_content = md_content + "    format: " + str(row['ds:DatAdditionalMaterialFormat']) + "\n"
            else:
                if str(project_row['ds:prjDocumentationName']) != "nan":
                    md_content = md_content + "  - name: " + str(project_row['ds:prjDocumentationName']) + "\n"
                    md_content = md_content + "    url: " + str(project_row['ds:prjDocumentationURL']) + "\n"
                    md_content = md_content + "    format: " + str(project_row['ds:prjDocumentationFormat']) + "\n"
                if str(project_row['ds:prjAdditionalMaterialName']) != "nan":
                    md_content = md_content + "  - name: " + str(project_row['ds:prjAdditionalMaterialName']) + "\n"
                    md_content = md_content + "    url: " + str(project_row['ds:prjAdditionalMaterialURL']) + "\n"
                    md_content = md_content + "    format: " + str(project_row['ds:prjAdditionalMaterialFormat']) + "\n"
                if str(row['ds:DatCodebookName']) != "nan":
                    md_content = md_content + "  - name: " + str(row['ds:DatCodebookName']) + "\n"
                    md_content = md_content + "    url: " + str(row['ds:DatCodebookURL']) + "\n"
                    md_content = md_content + "    format: " + str(row['ds:DatCodebookFormat']) + "\n"

                if str(row['ds:DatAdditionalMaterialName']) != "nan":
                    md_content = md_content + "  - name: " + str(row['ds:DatAdditionalMaterialName']) + "\n"
                    md_content = md_content + "    url: " + str(row['ds:DatAdditionalMaterialURL']) + "\n"
                    md_content = md_content + "    format: " + str(row['ds:DatAdditionalMaterialFormat']) + "\n"

            md_content = md_content + "download request:\n"
            if str(row['ds:DatDownloadRequestName']) != "nan":
                if str(project_row['ds:prjCollectionFacet']) == 'DiversityOne':
                    md_content = md_content + "  - name: " + str(row['ds:DatDownloadRequestName']) + "\n"
                    md_content = md_content + "    url: " + str(row['ds:DatDownloadRequestURL']) + "\n"
                    md_content = md_content + "    format: " + str(row['ds:DatDownloadRequestFormat']) + "\n"

                    #guidelines
                    md_content = md_content + "  - name: " + "Guidelines" + "\n"
                    md_content = md_content + "    url: " + "https://ds.datascientia.eu/marketplace/public/data-access-policy" + "\n"
                    md_content = md_content + "    format: " + "" + "\n"


                else:
                    md_content = md_content + "  - name: " + "" + "\n"
                    md_content = md_content + "    url: " + "" + "\n"
                    md_content = md_content + "    url: " + "" + "\n"



            md_content = md_content + "title: " + str(row['ds:DatName']) + "\n"
            md_content = md_content + "notes: " + str(row['ds:DatDescription']) + "\n"
            md_content = md_content + "ds:DatVersion: " + str(row['ds:DatVersion']) + "\n"
            md_content = md_content + f'ds:DatPublicationTimestamp: "{str(row["ds:DatPublicationTimestamp"])}"\n'
            md_content = md_content + "ds:DatLicense: " + str(row['ds:DatLicense']) + "\n"
            md_content = md_content + "ds:DatURL: " + str(row['ds:DatURL']) + "\n"
            md_content = md_content + "ds:DatKeyword: " + str(row['ds:DatKeyword']) + "\n"
            md_content = md_content + "ds:DatPublisher: " + str(row['ds:DatPublisher']) + "\n"
            md_content = md_content + "ds:DatCreator: " + str(row['ds:DatCreator']) + "\n"
            md_content = md_content + "ds:DatOwner: " + str(row['ds:DatOwner']) + "\n"
            md_content = md_content + "ds:DatLanguage: " + str(row['ds:DatLanguage']) + "\n"
            md_content = md_content + "ds:DatLevel: " + str(row['ds:DatLevel']) + "\n"
            md_content = md_content + "ds:DatSize: " + str(row['ds:DatSize']) + "\n"
            md_content = md_content + "ds:DatDomain: " + str(row['ds:DatDomain']) + "\n"
            md_content = md_content + "ds:DatFileFormat: " + str(row['ds:DatFileFormat']) + "\n"
            md_content = md_content + "ds:DatDetailedDescription: " + str(row['ds:DatDetailedDescription']) + "\n"
            md_content = md_content + "ds:DatDownloadRequest: " + str(row['ds:DatDownloadRequest']) + "\n"
            md_content = md_content + "ds:DatConditionsOfAccess: " + str(row['ds:DatConditionsOfAccess']) + "\n"
            md_content = md_content + "ds:DatGenre: " + str(row['ds:DatGenre']) + "\n"
            md_content = md_content + "ds:DatisAccessibleForFree: " + str(row['ds:DatisAccessibleForFree']) + "\n"
            md_content = md_content + "ds:DatExpires: " + str(row['ds:DatExpires']) + "\n"
            if str(row['ds:DatCategoryFacet']) == "Dataset":
                md_content = md_content + "ds:DatSensorName: " + str(row['ds:DatSensorName']) + "\n"
            md_content = md_content + "ds:DatType: " + str(row['ds:DatType']) + "\n"
            if str(row['ds:DatCategoryFacet']) == "Dataset":
                md_content = md_content + "ds:DatSensorType: " + "\n  - " + str(row['ds:DatSensorType']) + "\n"
            md_content = md_content + f'ds:DatStartDate: "{str(row["ds:DatStartDate"])}"\n'
            md_content = md_content + f'ds:DatEndDate: "{str(row["ds:DatEndDate"])}"\n'
            md_content = md_content + "ds:DatFiveStars: " + str(row['ds:DatFiveStars']) + "\n"
            md_content = md_content + "ds:DatOrigin: " + str(row['ds:DatOrigin']) + "\n"
            md_content = md_content + "ds:DatCreativeWorkStatus: " + str(row['ds:DatCreativeWorkStatus']) + "\n"
            md_content = md_content + "ds:DatIdentifier: " + str(row['ds:DatIdentifier']) + "\n"
            md_content = md_content + "ds:DatChangelogURL: " + str(row['ds:DatChangelogURL']) + "\n"
            md_content = md_content + "license: " + ">-\n  " + str(row['ds:DatLicenceURL']) + "\n"
            md_content = md_content + "ds:DatSha256: " + str(row['ds:DatSha256']) + "\n"
            md_content = md_content + "ds:DatUpdateTimestamp: " + str(row['ds:DatUpdateTimestamp']) + "\n"
            md_content = md_content + "ds:DatBasedOn: " + str(row['ds:DatBasedOn']) + "\n"

            # md_content = md_content + "resources:\n"
            # if str(row['ds:DatCodebookName']) != "nan":
            #     md_content = md_content + "  - name: " + str(row['ds:DatCodebookName']) + "\n"
            #     md_content = md_content + "    url: " + str(row['ds:DatCodebookURL']) + "\n"
            #     md_content = md_content + "    format: " + str(row['ds:DatCodebookFormat']) + "\n"

            # md_content = md_content + "project_url: <a href=\"" + str(row['project_url']) + "\">" + str(
            #     row['project_url']) + "</a>\n"

            # facet
            md_content = md_content + "duration_facet: " + f'"{str(row["ds:DatDurationFacet"])}"' + "\n"
            md_content = md_content + "location_facet: " + str(row['ds:DatLocationFacet']) + "\n"
            md_content = md_content + "collection_name: " + str(project_row['ds:prjCollectionFacet']) + "\n"
            md_content = md_content + "data_type_facet: " + str(row['ds:DataTypeFacet']) + "\n"
            md_content = md_content + "category: " + str(row['ds:DatCategoryFacet']) + "\n"

            # for viz
            if str(row['ds:DatCategoryFacet']) == "Dataset Bundle":
                md_content = md_content + "component_dataset_link: " + generate_html_href('Dataset Bundle', row,
                                                                                          all_df) + "\n"

            md_content = md_content + "---\n"

            output_file_path = os.path.join(output_dir, file_name)

            with open(output_file_path, 'w', encoding='utf-8') as md_file:
                md_file.write(md_content)
                cnt = cnt + 1
        except Exception as e:
            print(f"Error processing file {file_name}: {e}")

    print(f'total # generated md: {cnt}, with skipped: {skipped}')


def main(excel_path, output_dir):
    # step 1. get fields to generate project/dataset/dataset bundle
    # step 2. convertion on the existing to new
    # step 3. dynamic functions
    # step 4. facet creation

    # read by default 1st sheet of an excel file
    all_sheets = pd.read_excel(excel_path, sheet_name=None)  # None reads all sheets
    # df = pd.concat(all_sheets.values(), ignore_index=True)

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # project
    try:
        create_project_md(all_sheets['Project'], all_sheets)

        create_dataset_md(all_sheets['Dataset'], all_sheets)
        #
        create_dataset_md(all_sheets['Dataset Bundle'], all_sheets)
    except Exception as ex:
        print(ex)

    print(f"Markdown files generated in: {output_dir}")


if __name__ == "__main__":
    # Folder containing the Markdown files
    excel_path = "/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/sources/catalog.xlsx"

    # Output path
    output_dir = "/Users/munkhdelger/Knowdive/LivePeople/_datasets"
    # output_dir = "/Users/munkhdelger/Knowdive/LivePeople/resources/metadata_process_scripts/md_new"

    main(excel_path, output_dir)
