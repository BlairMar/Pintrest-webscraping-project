from typing import Union, List, Set
from pandas.core.frame import DataFrame
from selenium import webdriver
from time import sleep
import urllib.request
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC 
import json

from sqlalchemy.engine.base import Engine
# from webdriver_manager.chrome import ChromeDriverManager
import boto3 
from tqdm import tqdm
import shutil
import uuid
import re
import pandas as pd
from sqlalchemy import create_engine
import sys
from selenium.webdriver.chrome.options import Options

''' Defines a class to perform webscraping for the pinterest website. '''

class PinterestScraper:

    def __init__(self, root: str, category = None) -> None:
        
        ''' Initialise the attributes of the class

            Arguments
            ---------
            root: str (The main page which contains a list of all the available categories.) 

            Attributes
            ---------
            category: str \n
            root: str \n
            driver: webdriver object \n
            link_set: set \n
            log: set \n
            s3_list: list \n
            current_dict: dict \n
            main_dict: dict \n
            counter_dict: dict \n
            cat_imgs_to_save: dict \n
            s3_client: boto3.client(s3) \n
            xpath_dict: dict \n 

            Returns
            ---------
            None '''
            
        
        self.category = None # Holds the value whatever category we are currently on.
        self._root = root # The root URL.
        chrome_options = Options()
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self._driver = webdriver.Chrome(options=chrome_options)
        # self._driver = webdriver.Chrome(ChromeDriverManager().install())
        self._link_set = set() # A set to store previously visited pages' hrefs.
        self._log = set() # A set used to load previously visisted pages' hrefs upon a rerun.
        self._s3_list = [] # A list used to store the names of categories which are to be saved to an s3 bucket.
        self._current_dict = {} # A dictionary to store data for each individual image page.
        self._main_dict = {} # A dictionary to store data for entire categories.
        self._counter_dict = {} # A dictionary to define the start point for each category on subsequent runs.
        self._cat_imgs_to_save = {} # A dictionary which store which categories to download images for on a given run.
        self._s3_client = boto3.client('s3') # S3 client to connect to AWS S3.
        self._xpath_dict = { # A dictionary to store xpaths to various page elements.
            'official_user_container': '//div[@data-test-id="official-user-attribution"]',
            'official_user_element': './/div[@class="tBJ dyH iFc yTZ pBj zDA IZT mWe CKL"]',
            'non_off_user_container': '//div[@data-test-id="user-rep"]',
            'non_off_user_element': './/div[@class="tBJ dyH iFc yTZ pBj zDA IZT mWe"]',
            'follower_element': './/div[@class="tBJ dyH iFc yTZ pBj zDA IZT swG"]',
            'tag_container': '//div[@data-test-id="CloseupDetails"]',
            'story_tag_container': '//div[@data-test-id="CloseupMainPin"]',
            'tag_vase_carousel': '//div[@data-test-id="vase-carousel"]',
            'tag_link': './/div[@data-test-id="vase-tag"]//a',
            'reg_title_element': '//div[@data-test-id="CloseupDetails"]//div[@data-test-id="pinTitle"]/h1/div',
            'h1_title_element': '//div[@data-test-id="CloseupMainPin"]//h1',
            'desc_container': '//div[@data-test-id="CloseupDetails"]//div[@data-test-id="CloseupDescriptionContainer"]',
            'desc_element': './/span[@class="tBJ dyH iFc yTZ pBj zDA IZT swG"]',
            'links_container': '//div[@data-test-id="grid"]//div[@class="vbI XiG"]',
            'links_element': './/div[@class="Yl- MIw Hb7"]/div/div/div/div[1]/a',
            'categories_container': '//div[@data-test-id="interestRepContainer"]',
            'pin_closeup_image': '//div[@data-test-id="pin-closeup-image"]//img',
            'story_pin_image': '//div[@aria-label="Story Pin image"]',
            'story_pin_video': '//div[@data-test-id="story-pin-closeup"]//video',
            'story_pin_multi_video': '//div[@data-test-id="story-pin-closeup"]//video',
            'close_up_details': '//div[@data-test-id="CloseupDetails"]'
        }

        self._driver.get(self._root) # Opens the root URL.
        self._argsv = sys.argv

    def _get_category_links(self, categories_xpath: str) -> dict:
        
        ''' Defines a fucntion which extracts the href attribute
        of each category on the root URL page. 
        
        Arguments
        ---------
        categories_xpath: str (The xpath to the web element containing the container for the category page links.)

        Returns
        ---------
        dict (A dictionary containing the href for each category.) '''

        # Get the a list of all the categories on the root.
        try:
            # Wait until the presence of desired element is located or 2 seconds pass.
            container = WebDriverWait(self._driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, categories_xpath))
                )
            categories = container.find_elements_by_xpath('.//a')
            # Extract the href.
            return {i+1:link.get_attribute('href') for i, link in enumerate(categories)}

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _print_options(self, category_link_dict: dict) -> None:
        
        ''' Defines a function which prints all of the available categories
        on the root URL page. 

        Arguments
        ---------
        category_link_dict: dict (A dictionary containing the hrefs to each category presented on the root page.)
        
        Returns
        ---------
        None '''

        try:
            print(f"\n The options (Total {len(category_link_dict)}) are:")
            # Print all categories available on the root page.
            for idx, category in category_link_dict.items():
                print(f"\t {idx}: {category.replace(self._root, '').split('/')[0]}")

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _categories_to_save_imgs(self, selected_category_names: list) -> None:

        ''' Defines a function which asks the user which categories they would like to download images for.
        These categories are then saved to cat_images_to_save as either True, to be downloaded, or False,
        which are not downloaded. 

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        None'''

        try:
            # Ask the user if they would like to download any images at all.
            get_any = ''
            while get_any != 'N' and get_any != 'Y':
                get_any = self._argsv[3].upper()
                # If yes, ask them which categories they would like to download images for.
                if get_any == 'Y':
                    # Create the start of an input check list to ensure correct input is obtained.
                    print('A = All categories: ')
                    download_check = ['A']
                    # Add an option for each category that has been selected to grab data for.
                    for index, category in enumerate(selected_category_names):
                        print(f'{index + 1} = {category}')
                        download_check.append(str(index + 1))
                    while True:
                        # Ask which categories they would like to download images for.
                        try:
                            downloads = self._argsv[4].upper()
                            # Split the string input into a list of inputs.
                            downloads = (downloads.replace(' ', '')).split(',')
                            # Create an empty list to append inputs to, to ensure no repeated inputs.
                            repeat_check = []
                            for option in downloads:
                                # Append each input in to the repeat check list.
                                repeat_check.append(option)
                                # Ensure that the input is acceptable.
                                assert option in download_check
                            # Check that no repeats were in the user input.
                            assert len(repeat_check) == len(set(repeat_check))
                            # If the user wants to download all images.
                            if 'A' in downloads:
                                for cat_name in selected_category_names:
                                    self._cat_imgs_to_save[cat_name] = True
                            else:
                                # If they don't want to download images for all categories.
                                for option in downloads:
                                    self._cat_imgs_to_save[selected_category_names[int(option) - 1]] = True
                                # Ensure dictionary is update even for categories the user doesn't want to download.
                                for name in selected_category_names:
                                    if name not in self._cat_imgs_to_save.keys():
                                        self._cat_imgs_to_save[name] = False
                            # Print what the user has chosen to download images for (if any).
                            print_list = [key for key, value in self._cat_imgs_to_save.items() if value == True]
                            print(f'\nDownloading images for {print_list}')
                            break
                        except KeyboardInterrupt:
                            raise KeyboardInterrupt
                        # If the user input did not fulfill the parameters set above.
                        except:
                            print('\nPlease only select options from the provided list. No duplicates. ')
                # If they user does not want to download any images.
                elif get_any == 'N':
                    print('\nNo images will be downloaded. ')
                    for cat_name in selected_category_names:
                        self._cat_imgs_to_save[cat_name] = False
                # If they user did not choose Y or N.
                else:
                    print('\nNot a supported input. Please retry: ')

        except KeyboardInterrupt:
            raise KeyboardInterrupt


    def _get_user_input(self, category_link_dict: dict) -> tuple: 

        ''' Defines a function which asks the user how many and which categories
        to download. 

        Arguments
        ---------
        category_link_dict: dict (A dictionary containing the hrefs to each category presented on the root page.)
        
        Returns
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.) \n
        selected_category: dict (A dictionary of the categories in the current run as values to indexed keys.) '''

        # Ask the user how many of the printed categories they would like to grab data for.
        try: 
            while True:
                try:
                    categories_num = int(self._argsv[1])
                    # Ensure a valid answer. 
                    assert 0 < categories_num <= len(category_link_dict)
                    break
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:  
                    print(f"\nInvalid input, try again.") 

            selected_category = {}
            # If chosen number == max amount.
            if categories_num == len(category_link_dict):
                # Set empty dict to dict of full categories available for selection.
                selected_category = category_link_dict
            else:
                try:
                    choices = []
                    # Create a list of numbers 1 through total number of categories available.
                    check_list = [str(x+1) for x in range(len(category_link_dict))]
                    # Have user select what categories they want data for if not all categories.
                    while len(choices) != categories_num:
                        choices = self._argsv[2]
                        # Turn user input into correct list format.
                        choices = (choices.replace(' ', '')).split(',')
                        # Print out the users choices.
                        print(choices)
                        # Check the validity of each input in the users list.
                        for choice in choices:
                            # If the input is not valid, restart the loop.
                            if choice not in check_list:
                                choices = []
                                print(f'\nPlease only enter integers in a comma separated \
list. Values between 1 and {len(category_link_dict)}: ') 
                                break
                        # Ensure a choice is made.
                        if len(choices) == 0:
                            continue
                        # Ensure the number of choices match the number of categories user previously requested.
                        elif len(choices) != categories_num:
                            print('\nPlease only select the predetermined number of choices. ')
                        # Ensure that only unique inputs are allowed.
                        elif len(set(choices)) != len(choices):
                            print('\nOnly unique categories accepted. ')
                            choices = []
                        # If requirements are met, add the category name as the value to a Key of 1 -> number of selected categories.
                        elif len(set(choices)) == len(choices) == categories_num:
                            for i, choice in enumerate(choices):
                                choice = int(choice)
                                selected_category[i+1] = category_link_dict[choice]
                        else: 
                            print('\nUnknown choice error')  
                except KeyboardInterrupt:
                    raise KeyboardInterrupt          
                except:
                    raise Exception(f"\nChoice error 2")
            # Create a list of category names without the /*numberstring following the name.
            selected_category_names = [category.split('/')[4] for category in selected_category.values()]
            print(f"Categories selected: {selected_category_names}")

            return selected_category_names, selected_category

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def create_RDS(self) -> None:

        ''' Defines a function which asks the user if they would like to create an RDS.
        If the user says yes, asks whether the RDS should be local or remote. 

        Arguments
        ---------
        None 
        
        Returns
        ---------
        None '''

        try:
            # Ask the user if they would like to create an RDS.
            valid = False
            while not valid:
                rds_answer =  self._argsv[11].upper()
                if rds_answer == 'Y' or rds_answer == 'N':
                    # Answer is valid, stop the loop.
                    valid = True
                    if rds_answer == 'Y':
                        print('Creating RDS...')
                        # Ask whether to create/update tables on AWS RDS or local RDS.
                        remote_RDS = self._argsv[12].upper()
                        # Create/update remote RDS.
                        if remote_RDS == 'Y': 
                            self._json_to_rds('../data/', True)
                        # Create/update local RDS.
                        elif remote_RDS == 'N': 
                            self._json_to_rds('../data/', False)
                        else:
                            print('Invalid answer')
                    else:
                        print('Data will not be saved in an RDS...')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _interior_cloud_save_loop(self, remote: str, selected_category_names: list) -> Union[None, str]:

        ''' Defines a the interior loop of the overall cloud save function. Interior loop is designed and 
        intergrated so that the first question of the full loop is only asked once if an error is made when 
        typing the name of the desired s3 bucket. 

        Arguments
        ---------
        remote: str (Y or N or other use input from the exterior function '_save_to_cloud_or_local'.) \n
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        str ('retry' or '' depending on where the loop is broken to pass this back to the external function.) \n
        None (If the loop is broken somewhere where a str is not returned.) '''

        try:
            # If user wants to save data to an S3 bucket, gets the name of the bucket.
            if remote == 'Y':
                self.s3_bucket = self._argsv[6]
                # Shows the user the input to check that there are no mistakes in their entry. Asks to continue.
                go_on = ''
                while go_on != 'Y' and go_on != 'N':
                    go_on = self._argsv[7].upper()
                    # If they user is happy with their entry.
                    if go_on == 'Y':
                        # Creates a printed list and a check list for the user's next input.
                        print('A = All categories: ')
                        upload_check = ['A']
                        for index, category in enumerate(selected_category_names):
                            print(f'{index + 1} = {category}')
                            upload_check.append(str(index + 1))
                        while True:
                            try:
                                # Asks the user what categories they wopuld like to download to the S3 bucket.
                                all_or_some = self._argsv[8].upper()
                                # Turns the input into a valid list.
                                all_or_some = (all_or_some.replace(' ', '')).split(',')
                                # Shows the user their choices.
                                print(all_or_some)
                                # Creates an empty list to append to in order to check for repeat inputs from the user.
                                repeat_check = []
                                for option in all_or_some:
                                    # Append each input in the user's list to the repeat check.
                                    repeat_check.append(option)
                                    # Ensure input is valid.
                                    assert option in upload_check
                                # Ensure no repeats.
                                assert len(repeat_check) == len(set(repeat_check))
                                # If they user wants to upload everything to S3. Creates a list of all current run categories.
                                if 'A' in all_or_some:
                                    self._s3_list = selected_category_names
                                # If the user only wants specific categories to be uploaded to S3.
                                else:
                                    # Creates a list of selected categories.
                                    for option in all_or_some:
                                        self._s3_list.append(selected_category_names[int(option) - 1])
                                break
                            except KeyboardInterrupt:
                                raise KeyboardInterrupt
                            except:
                                print('\nPlease only select options from the provided list. No duplicates. ')
                    # If the user made a mistake when entering their bucket or wants to change bucket.
                    elif go_on == 'N':
                        print('\nPlease re-enter the name of your bucket. ')
                        # Returns to the exterior script a string which in turn will repeat the above code.
                        return 'retry'
            # If the user doesn't want to upload anything to S3 move on with the script.
            elif remote == 'N':
                print('\nAll data will be stored on your local machine. ')
            else:
                print('\nYour selection was not valid, please choose again. ')
                return ''
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _save_to_cloud_or_local(self, selected_category_names: list) -> None:

        ''' Defines a function which asks if the user wants to upload any data/images to an S3 bucket. 

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        None '''

        try:
            remote = ''
            # Asks if the user wants to upload anything to S3.
            while remote != 'N' and remote != 'Y':
                # If this is the first time running the function, or they made an inccorect entry last time.
                if remote == '':
                    remote = self._argsv[5].upper()
                    # Go to the interior loop.
                    remote = self._interior_cloud_save_loop(remote, selected_category_names)
                    # If the interior loop was completed successfully.
                    if remote == None:
                        break
                # If the user made a mistake in entering the name of their bucket.
                elif remote == 'retry':
                    remote = 'Y'
                    # Go back to the interior loop without repeating the first part of this function.
                    remote = self._interior_cloud_save_loop(remote, selected_category_names)
                    # If the interior loop was completed successfully.
                    if remote == None:
                        break
                else:
                    print('\nLoop structure error. Luke you stupid...')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _initialise_local_folders(self, directory_path: str, selected_category_names: list) -> None:

        ''' Defines a function which initialises folders for local saves. 

        Arguments
        ---------
        directory_path: str (A str indicating the location of the folder containing the src folder this file runs from.) \n
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        None '''

        try:
            # Assign the directory path to attribute for later use.
            self._root_save_path = directory_path

            print(f"\nCreating folders. ")

            for category in selected_category_names:
                # Creates a folder named data to store a folder for each category
                if not os.path.exists(f'{self._root_save_path}'):
                    os.makedirs(f'{self._root_save_path}')
                # Initialises a key with an empty dictionary value for each category in the current run for the main dictionary.
                self._main_dict[f"{category}"] = {}
                # Makes a temporary storage folder for every category in the current run.
                os.makedirs(f'{self._root_save_path}/temp_{category}')
        except KeyboardInterrupt:
            raise KeyboardInterrupt
            
    def _initialise_counter(self, selected_category_names: list) -> dict:

        ''' Defines a function which initialises the counter dictionary. 

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        dict (The counter dictionary this function initialises.) '''

        try:
            # Initialises the count for each category in current run.
            for category in selected_category_names:
                self._counter_dict[f'{category}'] = 0

            return self._counter_dict

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _check_for_logs(self, selected_category_names: list) -> Union[str, None]:

        ''' Defines a function which checks for data relating to a previous run of this script.
        If the logs are found, use these to initialise the scraper dictionaries if the current
        categories relate at all to the previous save data. 

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)
        
        Returns
        ---------
        fresh: Union[str, None] ('Y' or 'N' if previous save data is detected and the user chooses so. \
        None if no data relates to current run.) '''

        try: 
            # If there is has been a previous run and the logs are still on the system.
            if os.path.exists('../data/recent-save-log.json'):
                # Loads the log regarding location of save data.
                with open('../data/recent-save-log.json', 'r') as load:
                    recent_saves = json.load(load)
                # Gets the categories relating to the current run from the save data.
                saves = [key for key in recent_saves if key in selected_category_names]
                # Loads the log regarding web pages already visited as to not repeat data collection.
                with open('../data/log.json', 'r') as load:
                    contents = json.load(load)
                    # Save data in log is saved as the href collected and the related category.
                    tuples_content = [(item[0], item[1]) for item in contents]
                # If any data relates to current run print which categories they are.
                if saves:
                    print(f'\nWe have detected saved data for the follow categories: {saves}. ')
                    fresh = ''
                    # Asks the user if they would like to append to existing data to start afresh.
                    while fresh != 'Y' and fresh != 'N':
                        fresh = self._argsv[9].upper()
                        # If user wants to append, update link set and log with the hrefs previously visited.
                        if fresh == 'Y':
                            self._link_set = set(tuples_content)
                            self._log = set(tuples_content)
                            # Increase the counter dictionary for each category to the correct starting point.
                            for cat, href in tuples_content:
                                category = cat.split('/')[0]
                                if category in selected_category_names:
                                    self._counter_dict[category] += 1
                            for save in saves:
                                # If a category has a local save file, load the associated json data into the main dictionary.
                                if recent_saves[save] == 'local':
                                    with open(f'../data/{save}/{save}.json', 'r') as load:
                                        self._main_dict[f'{save}'] = json.load(load)
                                # If a category has a remote save file, load the associated json data into the main dictionary.
                                elif recent_saves[save][0] == 'remote':
                                    obj = self._s3_client.get_object(
                                        Bucket = recent_saves[save][1],
                                        Key = (f'pinterest/{save}/{save}.json')
                                    ) 
                                    self._main_dict[f'{save}'] = json.loads(obj['Body'].read())
                                else: 
                                    print('\nSomething fishy going on with the save_log. ')
                        # If the user wants to start anew for current run categories, ensure data for categories not in this run
                        # remains intact while removing data relating to current run categories.
                        elif fresh == 'N':
                            tuples_content = [item for item in tuples_content if item[0].split('/')[0] not in saves]
                            self._link_set = set(tuples_content)
                            self._log = set(tuples_content)
                        else:
                            print('\nPlease re-enter your input. ')
                # If there is save data but none relates to current run categories, ensure data is maintained.
                else:
                    self._link_set = set(tuples_content)
                    self._log = set(tuples_content)
                    fresh = None
                    print("\nPrevious saves detected: None relate to this data collection run. ")
            # If no previous save data was found. 
            else:
                fresh = None

            return fresh

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _extract_links(self, container_xpath: str, elements_xpath: str, n_scrolls: int = 1) -> None:

        ''' Defines a function which scrolls through the page relating to every category in the current run.
        With each scroll it grabs the href of each image page that it finds and appends it to a set of hrefs. 

        Arguments
        ---------
        container_xpath: str (The xpath for the web element which contains all the images on the page being scraped.) \n
        elements_xpath: str (The xpath regarding the <a> tags which contain the hrefs the method gaathers.) \n
        n_scrolls: int (The number of times a user wishes to scroll down each category page.)

        Returns
        ---------
        None '''

        try:
            # Opens the page for a category.
            self._driver.get(self._root + self._category)
            # Sets the maximum amount of pixels allowed for one scroll.
            Y = 10**6    
            sleep(2)
            # Keep scrolling down teh specified number of times.
            for _ in range(n_scrolls):
                # Scrolls down the page.
                self._driver.execute_script(f"window.scrollTo(0, {Y})")
                sleep(1)
                try:
                    # Stores the href to each image page if the page contains the desired images.
                    container = self._driver.find_element_by_xpath(container_xpath)
                    link_list = container.find_elements_by_xpath(elements_xpath)
                    # Displays the images grabbed in a specific scroll.
                    print(f"\nNumber of images successfully extracted: {len(link_list)}")
                    # Appends the hrefs to a set.
                    self._link_set.update([(self._category, link.get_attribute('href')) for link in link_list])
                    # Displays the total number of unique hrefs after every scroll.
                    print(f"\nNumber of images unique to this run: {len(self._link_set) - len(self._log)}")
                except: 
                    # If the page contains no images, or there is an error loading image elements on a page, skip the category.
                    print('\nNo images detected on this page. Moving to next page (if applicable). ')
                    # Leaves a message in the dictionary to explain why there is no data.
                    self._main_dict[self._category.split('/')[0]]['Message'] = 'No image data available for this category on this run. \
\nThere may not be any images on this page or there may have been an error.'
                    break
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_images_src(self, selected_category: dict, n_scrolls: int = 1) -> None:

        ''' Defines a function which grabs all the hrefs for all the images to be grabbed during the run.

        Arguments
        ---------
        selected_category: dict (A dictionary of the categories in the current run as values to indexed keys.) \n
        n_scrolls: int (The number of times a user wishes to scroll down each category page.)

        Returns
        ---------
        None '''

        try:
            # Loops through each category and runs extract_links to grab hrefs.
            for category in selected_category.values():
                self._category = category.replace(self._root, "")
                self._extract_links(self._xpath_dict['links_container'], 
                                    self._xpath_dict['links_element'],
                                    n_scrolls)
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _generate_unique_id(self) -> None:

        ''' Defines a function which generates a unique ID (uuid4) for every image page
        that is scraped by the scraper. 

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            # Generates a uuid4.
            self._current_dict['unique_id'] = str(uuid.uuid4())

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_title(self, title_element: str) -> None:

        ''' Defines a function that grabs the title from a Pinterest page and adds it to the key
        "title" in self._current_dict. 

        Arguments
        ---------
        title_element: str (The xpath that leads to the title web element of a given Pinterest page.)

        Returns
        ---------
        None '''

        try:
            # Finds the title web element of a page and assigns it to the dictionary of the current page data.
            try:
                title_element = self._driver.find_element_by_xpath(title_element)
                self._current_dict["title"] = title_element.get_attribute('textContent')
            # No title element found.
            except:
                self._current_dict["title"] = 'No Title Data Available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        
    def _grab_description(self, desc_container, desc_element) -> None:

        ''' Defines a function that grabs the description from a Pinterest page and adds it to the key
        "description" in self._current_dict. 

        Arguments
        ---------
        desc_container: str (The xpath for the web element which contains the description section of the page.) \n
        desc_element: str (The xpath that leads to the description web element following the container xpath.)

        Returns
        ---------
        None '''

        try: 
            # Grabs the container of the description box.
            description_container = self._driver.find_element_by_xpath(desc_container)
            # Tries to grab the desctiption if it is present. If not, no description available.
            try:
                description_element = WebDriverWait(description_container, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, desc_element))
                )
                self._current_dict["description"] = description_element.get_attribute('textContent')
            # No description available.
            except:
                self._current_dict["description"] = 'No description available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_user_and_count(self, dict_container, dict_element) -> None:

        ''' Defines a function that grabs the poster name and follower count and appends adds them to the keys
        "poster_name" and "follower_count" respectively in self._current_dict. 

        Arguments
        ---------
        dict_container: str (The xpath for the web element which contains the user information section of the page.) \n
        dict_element: str (The xpath that leads to the description web element following the container xpath.)

        Returns
        ---------
        None '''

        try:
            try:
                # Grabs the poster name and assigns to current dict.
                container = self._driver.find_element_by_xpath(dict_container)
                poster_element = container.find_element_by_xpath(dict_element)          
                self._current_dict["poster_name"] = poster_element.get_attribute('textContent')
                # Grabs the follower count and assigns to current dict.
                follower_element =  container.find_elements_by_xpath(self._xpath_dict['follower_element'])
                followers = follower_element[-1].get_attribute('textContent')
                # If the element has no associated text, there are no followers.
                if followers == '':
                    self._current_dict["follower_count"] = '0'
                # Splits the text to only give the number of followers.
                else:
                    self._current_dict["follower_count"] = followers.split()[0]
            # If there is an error with the container for the user info update current dict accordingly.
            except:
                if 'poster_name' not in self._current_dict.keys():
                    self._current_dict['poster_name'] = 'User Info Error'
                if 'follower_count' not in self._current_dict.keys():
                    self._current_dict['follower_count'] = 'User Info Error'
                print('User Info Error')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_tags(self, tag_container) -> None:

        ''' Defines a function that grabs the tags from a Pinterest page and adds them to the key 
        "tag_list" in self._current_dict. 

        Arguments
        ---------
        tag_container: str (The xpath for the web element which contains the tags for the page.)

        Returns
        ---------
        None '''

        try:  
            try:
                # Waits for the tag container element to appear on the page.
                container = WebDriverWait(self._driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, f'{tag_container}{self._xpath_dict["tag_vase_carousel"]}'))
                )
                # Grabs the text content of each tag on the page.
                tag_elements = container.find_elements_by_xpath(self._xpath_dict['tag_link'])
                self._current_dict["tag_list"] = [tag.get_attribute('textContent') for tag in tag_elements]
            # If no tags are available on the page.
            except:
                self._current_dict["tag_list"] = 'No Tags Available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _download_image(self, src: str) -> None:

        ''' Defines a function that downloads the image on a page to the temp folder for it's respective category. 

        Arguments
        ---------
        src: str (The src link for the picture being downloaded.)

        Returns
        ---------
        None '''

        try:
            # If the category is one for which the user previously decided they wanted to download images for.
            if self._cat_imgs_to_save[self._category]:
                # Downloads the image to the appropriate folder.
                urllib.request.urlretrieve(src, 
                f"{self._root_save_path}/temp_{self._category}/{self._category}_{self._counter_dict[self._category]}.jpg")
            # If the image is not downloaded enter as such in current dict.
            else:
                self._current_dict['downloaded'] = False
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _is_img_downloaded(self) -> None:

        ''' Defines a function that appends whether the image has been downloaded or not to the current dict. 

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            # If there is not a key 'downloaded' from the _download_image method then the image has been downloaded.
            if 'downloaded' not in self._current_dict.keys():
                # Append information as such to the current page dict.
                self._current_dict['downloaded'] = True
            # If downloaded already exists, image has not been downloaded and has previously been noted as such, so pass.
            else:
                pass
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _save_location_key(self) -> None:

        ''' Defines a function that appends save location of a categories json file and potential images.

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            # If the category is to be saved remotely.
            if self._category in self._s3_list:
                # Append the bucket it will be saved to to the current dict.
                self._current_dict['save_location'] = f"S3 bucket: {self.s3_bucket}"
            else:
                # Else appends a local save.
                self._current_dict['save_location'] = f"Local save in /data/{self._category}"
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_image_src(self) -> None:

        ''' Defines a function that grabs the image src from a Pinterest page and adds it to the key 
        "image_src" in self._current_dict. 

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            try:
                try: 
                    # Waits for element to load as page layout can be determined by what elements load or not.
                    image_element = WebDriverWait(self._driver, 1).until(
                        EC.presence_of_element_located((By.XPATH, self._xpath_dict['pin_closeup_image']))
                    )
                    self._current_dict["is_image_or_video"] = 'image'
                    # If the element loads grab the image src.
                    self._current_dict["image_src"] = image_element.get_attribute('src')
                    # Download the image if user wants images downloaded for this category.
                    self._download_image(self._current_dict["image_src"])
                    # Appends if image has been downloaded or not to the current dict.
                    self._is_img_downloaded()
                    # Appends the save location of the image to the current dict.
                    self._save_location_key()
                except:
                    # If the element didn't load it means that the element is a video and not an image.
                    video_element = self._driver.find_element_by_xpath('//video')
                    self._current_dict["is_image_or_video"] = 'video'
                    # Grab a different web element specifically for videos.
                    self._current_dict["image_src"] = video_element.get_attribute('poster')
                    # Download the thumbnail of the video if the user wants images downloaded for this category.
                    self._download_image(self._current_dict["image_src"])
                    # Appends if thumbnail has been downloaded or not to the current dict.
                    self._is_img_downloaded()
                    # Appends the save location of the thumbnail to the current dict.
                    self._save_location_key()
            except:
                # If the nested try loop fails there is a page layout that we have not encountered before, hence the fail.
                self._current_dict['downloaded'] = False
                self._save_location_key()
                print('\nImage grab Error. Possible embedded video (youtube).')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_story_image_srcs(self) -> None:

        ''' Defines a function that grabs the image src from a Pinterest page that deviates from the usual 
         page layout and adds it to the key "image_src" in self._current_dict. 

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            try: 
                try:
                    # Waits until the image container element is present fails the try statement if it isn't present.
                    image_container = WebDriverWait(self._driver, 1).until(
                            EC.presence_of_element_located((By.XPATH, self._xpath_dict['story_pin_image']))
                        )
                    # Grabs the src for the image if the correct container was obtained.
                    image = image_container.get_attribute('style')
                    if not image:
                        # If the container didn't have the style attribute then it should have the poster attribute, i.e. a video page.
                        # Grabs the src for the thumbnail of the video on the page.
                        self._current_dict["is_image_or_video"] = 'video(story page format)'
                        video_container = self._driver.find_element_by_xpath(self._xpath_dict['story_pin_video'])
                        self._current_dict["image_src"] = video_container.get_attribute('poster')
                        # Downloads the image if the user wants to download images for this category.
                        self._download_image(self._current_dict["image_src"])
                        # Checks if the image has been downloaded and updates the currect page dict to save so.
                        self._is_img_downloaded()
                        # Appends the save location of the image to the current page dict.
                        self._save_location_key()
                    else: 
                        # If the style attribute is found then an image is present on the page.
                        self._current_dict["is_image_or_video"] = 'image(story page format)'
                        # The src grabbed earlier is embedded in more text, need to separate the src.
                        self._current_dict["image_src"] = re.split('\"', image)[1]
                        # Downloads the image if the user wants to download images for this category.
                        self._download_image(self._current_dict["image_src"])
                        # Checks if the image has been downloaded and updates the currect page dict to save so.
                        self._is_img_downloaded()
                        # Appends the save location of the image to the current page dict.
                        self._save_location_key()
                except:
                    # If the element at the start of the function does not load there is a different page format.
                    # Grabs and appends the src for the first thumbnail of the videos on the page to the current dict.
                    self._current_dict["is_image_or_video"] = 'multi-video(story page format)'
                    video_container = self._driver.find_element_by_xpath(self._xpath_dict['story_pin_multi_video'])
                    self._current_dict["image_src"] = video_container.get_attribute('poster')
                    # Downloads the image if the user wants to download images for this category.
                    self._download_image(self._current_dict["image_src"])
                    # Checks if the image has been downloaded and updates the currect page dict to save so.
                    self._is_img_downloaded()
                    # Appends the save location of the image to the current page dict.
                    self._save_location_key()
            except:
                # If none of the above elements are present on the page there is some form of page layout unencountered as of yet.
                # If the src has been grabbed but there was an error elsewhere, keep the src. If not, upload an error message.
                try:
                    if self._current_dict['image_src']:
                        pass
                except:
                    self._current_dict['image_src'] = 'Image src error.'
                # Appends that the image has not been downloaded
                self._current_dict['downloaded'] = False
                # Appends the save location of the image to the current page dict.
                self._save_location_key()
                print('\nStory image grab error.')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_all_users_and_counts(self) -> None:

        ''' Defines a function that checks if a user is officially recognised or a story. Then runs the appropriate 
        methods to grab the data based on what type of page layout is present on the page. 

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try: 
            # Sees if the page has the layout of an official user account.
            if (self._driver.find_elements_by_xpath(self._xpath_dict['official_user_container'])):
                # Generates a unique id for the current page dict.
                self._generate_unique_id()
                # Grabs the title of the page.
                self._grab_title(self._xpath_dict['reg_title_element'])
                # Grabs the description of the page.
                self._grab_description(self._xpath_dict['desc_container'], self._xpath_dict['desc_element'])
                # Grabs the user account name and the follower count of the page.
                self._grab_user_and_count(
                    self._xpath_dict['official_user_container'],
                    self._xpath_dict['official_user_element']
                )
                # Grabs the tags present on the page.
                self._grab_tags(self._xpath_dict['tag_container'])
                # Grabs the image src and downloads the image of the page if applicable.
                self._grab_image_src()
            # Sees if the page has the layout of a non official user account.
            elif (self._driver.find_elements_by_xpath(self._xpath_dict['close_up_details'])):
                # Generates a unique id for the current page dict.
                self._generate_unique_id()
                # Grabs the title of the page.
                self._grab_title(self._xpath_dict['reg_title_element'])
                # Grabs the description of the page.
                self._grab_description(self._xpath_dict['desc_container'], self._xpath_dict['desc_element'])
                # Grabs the user account name and the follower count of the page.
                self._grab_user_and_count(
                    self._xpath_dict['non_off_user_container'],
                    self._xpath_dict['non_off_user_element']
                )
                # Grabs the tags present on the page.
                self._grab_tags(self._xpath_dict['tag_container'])
                # Grabs the image src and downloads the image of the page if applicable.
                self._grab_image_src()
            # If none of the layouts above are present the page layout is likely that of a story post.
            else:
                # Generates a unique id for the current page dict.
                self._generate_unique_id()
                # Grabs the title of the page.
                self._grab_title(self._xpath_dict['h1_title_element'])
                # As far as it is possible to tell there are no descriptions available for the story post layout.
                self._current_dict["description"] = 'No description available Story format'
                # Grabs the user account name and the follower count of the page.
                self._grab_user_and_count(
                    self._xpath_dict['non_off_user_container'],
                    self._xpath_dict['non_off_user_element']
                )
                # Grabs the tags present on the page.
                self._grab_tags(self._xpath_dict['story_tag_container'])
                # Grabs the first image src and downloads the image of the page if applicable.
                self._grab_story_image_srcs()
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_page_data(self) -> None:

        ''' Defines a function which combines all data grab methods and loops through all page links 
        to grab the data from each page.

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        try:
            # Link set has hrefs appended during the run of the program, log defines the previously visited pages.
            # Only go to the pages that are in the current run set and not in the log.
            fresh_set = self._link_set.difference(self._log)
            for (cat, link) in tqdm(list(fresh_set)):
                # Grab only the name of the category to which the href belongs.
                self._category = cat.split("/")[0]
                # For every page we pass in a particular category increase the counter dictionary count of the category by 1.
                self._counter_dict[f"{self._category}"] += 1
                # Renew the current_dictionary for every page we visit.
                self._current_dict = {}
                # Go to the page for which we have the href.
                self._driver.get(link)
                # Grab all page data and download the image if applicable.
                self._grab_all_users_and_counts()
                # Append the current page dictionary to the main dictionary as a value to the key (category_(number of page in category list)).
                self._main_dict[f"{self._category}"][f"{self._category}_{self._counter_dict[self._category]}"] = self._current_dict
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _data_dump(self, selected_category_names: list) -> None:

        ''' Defines a function which dumps the compiled dictionary for each category to its respective folder to be saved
        as a json file.

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)

        Returns
        ---------
        None '''

        try:
            # If the data folder doesn't exist, create it and change directory to said data folder.
            if not os.path.exists('../data'):
                os.mkdir('../data')
            os.chdir('..')
            os.chdir('data')

            print('Dumping Data: ')
            # Dump the full dictionary for each category as a json file to its folder.
            for name in tqdm(selected_category_names):
                with open(f'temp_{name}/{name}.json', 'w') as loading:
                    json.dump(self._main_dict[f"{name}"], loading)

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _data_transferal(self, selected_category_names: list) -> None:

        ''' Defines a function which moves data from temp folders to it's final destination. Data is handled 
        in this way to remove errors when KeyboardInterrupting the scraping process. 

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)

        Returns
        ---------
        None '''

        try:

            print('Moving files around a bit... ')

            for category in tqdm(selected_category_names):
                # Define the path for the file containing run data for the current category.
                temp_path = f'../data/temp_{category}'
                # If data is to be saved locally.
                if category not in self._s3_list:
                    # Define the path which data will be stored in.
                    end_path = f'../data/{category}'
                    # If this is the first run ,or old data has been deleted via the users input.
                    if not os.path.exists(end_path):
                        # Simply rename the temp folder to the name of the final folder.
                        os.rename(temp_path, end_path)
                    # If end folder already exists from previous run
                    else:
                        # For every file in the temp folder, move it to the correct folder and delete the temp folder.
                        for file in os.listdir(temp_path):
                            shutil.move(f'{temp_path}/{file}', f'{end_path}/{file}')
                        shutil.rmtree(temp_path)
                # If the data is to be stored remotely.
                else:
                    # Define the path to save in the s3 bucket.
                    end_path = f'pinterest/{category}'
                    # For every file in the temp folder, move it to the correct place in the s3 bucket then delete the temp folder.
                    for file in os.listdir(temp_path):
                        self._s3_client.upload_file(
                            f'{temp_path}/{file}',
                            self.s3_bucket,
                            f'{end_path}/{file}'
                    )
                    shutil.rmtree(temp_path)
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _create_log(self, selected_category_names: list) -> bool:

        ''' Defines a function which creates two logs. One of which logs pages visited as to not repeat,
        the other a log of where the most recent save for each category is in order to update the most recent
        save on subsequent runs of the script.

        Arguments
        ---------
        selected_category_names: list (A list of all categories selected by the user for the current run.)

        Returns
        ---------
        bool (Returns as to whether the 2 logs have been succesfully created for testing purposes.) '''

        try:

            # if dict exists json.load
            print('Creating save logs: ')
            # If a save_log already exsists, load the log into a varibale in order to append to it before resaving.
            if os.path.exists('../data/recent-save-log.json'):
                with open('../data/recent-save-log.json', 'r') as load:
                    self.recent_save_dict = json.load(load)
            # If the save_log does not exists already, initiate en empty dictionary to store the data for the log.
            else:
                self.recent_save_dict = {}
            # For each category, check if the images should be saved remotely or locally.
            for category in tqdm(selected_category_names):
                # If saving remotely append the name of the bucket being saved to to the save_log.
                if category in self._s3_list:
                    update = ['remote', self.s3_bucket]
                # Else just say that the data was saved locally.
                else:
                    update = 'local'
                # Append the save location to the dictionary for each category being saved.
                self.recent_save_dict[category] = update
            # Open a context manager for both logs and dump the data to the approproate json file.
            with open('../data/log.json', 'w') as log, open('../data/recent-save-log.json', 'w') \
            as save:
                json.dump(list(self._link_set), log)
                json.dump(self.recent_save_dict, save)
            
            return os.path.exists('../data/log.json') and os.path.exists('../data/recent-save-log.json')

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _delete_old_files(self, fresh: str, selected_category_names: list) -> None:

        ''' Defines a function that deletes old save files if they become outdated.

        Arguments
        ---------
        fresh: Union[str, None] ('Y' or 'N' if previous save data is detected and the user chooses so. \
        None if no data relates to current run.) \n
        selected_category_names: list (A list of all categories selected by the user for the current run.)

        Returns
        ---------
        None '''

        try:
            # If previosu save data has been detected by the script.
            if fresh:
                # Loads the save file.
                with open('../data/recent-save-log.json', 'r') as load:
                    old_saves = json.load(load)
                # Grabs the save categories relating to the current run.
                saves = [key for key in old_saves if key in selected_category_names] 
                # For every category that relates to the current run.
                for save in saves:
                    # If the new data is to be saved remotely to the same remote bucket as the previous save data.
                    if save in self._s3_list and old_saves[save][0] == 'remote' \
                    and old_saves[save][1] == self.s3_bucket:
                        # If the user wants to delete olf data, remove all old data from the S3 bucket.
                        if fresh == 'N':
                            s3 = boto3.resource('s3')
                            bucket = s3.Bucket(old_saves[save][1])
                            bucket.objects.filter(Prefix=f"pinterest/{save}/").delete()
                    # If the new data is to be saved remotely but to a different bucket than the previous save.
                    elif save in self._s3_list and old_saves[save][0] == 'remote' \
                    and old_saves[save][1] != self.s3_bucket:
                        # Get the data from the previous bucket.
                        s3 = boto3.resource('s3')
                        src_bucket = s3.Bucket(old_saves[save][1])
                        target_bucket = s3.Bucket(self.s3_bucket)
                        print('Relocating previous bucket save files. ')
                        # For every item in the older bucket.
                        for src in tqdm(src_bucket.objects.filter(Prefix=f"pinterest/{save}/")):
                            # If continuing from old data, move old data to new bucket and delete data from old bucket.
                            if fresh == 'Y':
                                copy_source = {
                                    'Bucket': src_bucket.name,
                                    'Key': src.key
                                }
                                target_bucket.copy(copy_source, src.key)
                                src.delete()
                            # If not continuing from old save data, delete old data.
                            elif fresh == 'N':
                                src.delete()
                    # If data to be saved locally but previous save was remote.
                    elif save not in self._s3_list and old_saves[save][0] == 'remote':
                        # Grab all data from old bucket.
                        s3 = boto3.resource('s3')
                        src_bucket = s3.Bucket(old_saves[save][1])
                        print('Relocating previous bucket save files. ')
                        # For every item in old bucket.
                        for src in tqdm(src_bucket.objects.filter(Prefix=
                        f"pinterest/{save}/")):
                            # If continuing from old data, download remote data to correct local folder, delete data from bucket.
                            if fresh == 'Y':
                                src_bucket.download_file(src.key, 
                                f"../data/temp_{save}/{src.key.split('/')[2]}")
                                src.delete()
                            # If not continuing from old data, delete data from old bucket.
                            elif fresh == 'N':
                                src.delete()
                    # If new data to be saved locally and old data is also local. Pass unless not continuing from old data.
                    elif save not in self._s3_list and old_saves[save] == 'local':
                        # If not contunuing from old data, delete old data.
                        if fresh == 'N':
                            shutil.rmtree(f'../data/{save}')
                    # If new data to be saved remotely and old data is local.
                    elif save in self._s3_list and old_saves[save] == 'local':
                        # Grab the remote bucket.
                        s3 = boto3.resource('s3')
                        print('Relocating previous local save files. ')
                        # For every item in old local folder.
                        for item in tqdm(os.listdir(f'../data/{save}')):
                            # If continuing from old data, upload previous data to designated bucket and delete data from local
                            if fresh == 'Y':
                                self._s3_client.upload_file(f'../data/{save}/{item}', 
                                self.s3_bucket, f'pinterest/{save}/{item}')
                            # If not continuing from old data, delete old data.
                            elif fresh == 'N':
                                pass
                        shutil.rmtree(f'../data/{save}')
                    else: 
                        # If there is a mistake in above code and something goes wrong, abort script to save integrity of old data.
                        print('Missed a scenario in _delete_old_files. ')
                        self._driver.quit()

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _connect_to_RDS(self, remote: bool) -> Engine:

        ''' Defines a function which collects the connection information to an RDS in order to connect
        to said RDS.

        Arguments
        ---------
        remote: bool (A boolean to determine whether or not to create/connect to an RDS.)

        Returns
        ---------
        engine: Engine (The RDS engine to connect to the RDS and issue commands.) '''
        
        DATABASE_TYPE = 'postgresql'
        DBAPI = 'psycopg2'
        # Ask for user information from script user. If none given default to postgres.
        USER = self._argsv[13]
        if not USER:
            USER = 'postgres'
        # Asks the user for a conenction password.
        PASSWORD = self._argsv[14]
        
        # Asks the user for the connection port, if none given, default to 5433.
        PORT = self._argsv[15]
        if not PORT:
            PORT = 5433
        # Asks the user for the database name, if none given, default to Pagila.
        DATABASE = self._argsv[16]
        if not DATABASE:
            DATABASE = 'Pagila'
        # If the user wants to mae a remote RDS change the engine being created to support AWS RDS
        if remote:
            ENDPOINT = self._argsv[17]
            engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{ENDPOINT}:{PORT}/{DATABASE}")
        else:
            # Asks the user for the host, if none given, default to localhost.
            HOST = self._argsv[18]
            if not HOST:
                HOST = 'localhost'
            engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}")
        # Connect to the RDS
        engine.connect()

        return engine

    def _process_df(self, df) -> DataFrame:

        ''' Defines a function which rearranges the dataframe into the proper format before sending to the RDS.

        Arguments
        ---------
        df: dataframe (pandas dataframe to reformat.)

        Returns
        ---------
        df: dataframe (The pandas dataframe in the correct format to send to the RDS.) '''

        # Transpose the dataframe.
        df = df.T
        df['name'] = df.index
        # Make unique_id the index of the dataframe.
        df = df.set_index('unique_id')
        file_name_col = df.pop('name')
        df.insert(0, 'name', file_name_col)
        print(df.head(3))
        return df

    def _json_to_rds(self, data_path:str, remote: bool) -> None:

        ''' Defines a function which loads teh json files from both remote and local folders and turns
        the data in to an RDS.

        Arguments
        ---------
        data_path: str (The local path where json files are stored.) \n
        remote: bool (A boolean to determine whether or not to create/connect to an RDS.)

        Returns
        ---------
        None '''

        # Connect to RDS.
        engine = self._connect_to_RDS(remote)

        # Find all local JSON files.
        folders = os.listdir(data_path)
        recent_log = folders[folders.index('recent-save-log.json')]
        with open(data_path + '/' + recent_log) as log_file:
            recent_saves = json.load(log_file)

        # Check content of log to check if the data are on S3 or on local PC.
        for key, val in recent_saves.items():
            # For local JSON files.
            if type(val) == str: 
                json_path = data_path + '/' + key + '/' + key +'.json'
                print(json_path)
                # Load local JSON file as a dataframe.
                df = pd.read_json(json_path)
                df = self._process_df(df)
                df.to_sql(f'pinterest_{key}', engine, if_exists='replace')
            # For remote JSON files.
            elif type(val) == list: 
                # Load file from S3 bucket.
                json_obj = self._s3_client.get_object(
                    Bucket = val[1],
                    Key = (f'pinterest/{key}/{key}.json')
                )
                save_dict = json.loads(json_obj['Body'].read())
                # Load as a dataframe.
                df = pd.DataFrame.from_dict(save_dict)
                df = self._process_df(df)
                df.to_sql(f'pinterest_{key}', engine, if_exists='replace')

    def get_category_data(self) -> None:

        ''' Defines a public function which combines all of the previously defines methods in order to scrape
        the pinterest page how the user defines.

        Arguments
        ---------
        None

        Returns
        ---------
        None '''

        # External try loop for KeyboardInterrupt robustness.
        try:
            # Get the categories on the root page.
            category_link_dict = self._get_category_links(self._xpath_dict['categories_container'])
            sleep(0.75)
            # Display categories as options to the user.
            self._print_options(category_link_dict)
            # Asks the user what categories they would like to scrape.
            selected_category_names, selected_category = self._get_user_input(category_link_dict)
            # Asks the user what categories they would like to download images for.
            self._categories_to_save_imgs(selected_category_names)
            # Asks the user if they would like to save any data to the cloud.
            self._save_to_cloud_or_local(selected_category_names)
            # Initialises counter dict and temp save folders.
            self._initialise_counter(selected_category_names)
            self._initialise_local_folders('../data', selected_category_names)
            # Searches for previosu save data.
            fresh = self._check_for_logs(selected_category_names)
            # Asks the user how many times they would like to scrill through each category page.
            while True:
                try:
                    scrolling_times = int(self._argsv[10])
                    break
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:
                    print('Invalid input, try again: ')
            # Grabs the hrefs for the images/data to be grabbed.
            self._grab_images_src(selected_category, n_scrolls=scrolling_times)
            # Grabs data for every href saved.
            self._grab_page_data()
            # Deletes redundant data.
            self._delete_old_files(fresh, selected_category_names)
            # Saves data dictionaries as JSON files.
            self._data_dump(selected_category_names)
            print('Please do not end the script now. May cause errors with later runs. ')
            # Moves data from temp save folders to final destination.
            self._data_transferal(selected_category_names)
            # Creates logs of the data collection for subsequent runs.
            log_created = self._create_log(selected_category_names)
            self._driver.quit()
        # If there is a keyboard interrupt, preserve old save integrity and delete any new run data.
        except KeyboardInterrupt:
            print('\nTerminating Script.\nRemoving any accumulated data. ')
            try:
                if selected_category_names:
                    for category in tqdm(selected_category_names):
                        if os.path.exists(f'../data/temp_{category}'):
                            shutil.rmtree(f'../data/temp_{category}')
            finally:
                exit()

if __name__ == "__main__": 

    # Initiate the scraper.
    pinterest_scraper = PinterestScraper('https://www.pinterest.co.uk/ideas/')
    # Run the scraper.
    pinterest_scraper.get_category_data()
    # Create RDS from collected data.
    pinterest_scraper.create_RDS()