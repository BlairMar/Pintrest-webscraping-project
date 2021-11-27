from typing import Union, List, Set
from selenium import webdriver
from time import sleep
import urllib.request
import os
from collections import defaultdict
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC 
import json
# from webdriver_manager.chrome import ChromeDriverManager
import tempfile
import boto3 
from tqdm import tqdm
import shutil
import uuid
import re
import pandas as pd
from sqlalchemy import create_engine

"""
Class to perform webscraping on the Pinterest website.
"""
class PinterestScraper:

    def __init__(self, root):
        """
        Initialise the attributes of the class

        Args
        ----------------------------------------------------------------
        root: str \n
                The main page which contains a list of all the
             available categories

        Attributes
        ---------------------------
        category: str \n
        root: str \n
        driver: webdriver object \n
        image_set: list \n
        category_link_list: list \n
        save_path: str \n
        link_set: set \n
        current_dict: dict \n
        main_dict: dict \n
        current_link: str \n
        xpath_dict: dict \n
        """
        
        self._category = None
        self._category_image_count = defaultdict(int)
        self._root = root
        self._driver = webdriver.Chrome()
        # self._driver = webdriver.Chrome(ChromeDriverManager().install())
        self._image_set = set()
        self._save_path = None
        self._link_set = set()
        self._log = set()
        # self.fresh_set = set() # No need to define as attribute if the set is used in only one class
        self._s3_list = []
        # self.current_run_categories = [] # Made redundant by self.selected_category_names
        self.selected_category_names = None
        self._current_dict = {}
        self._main_dict = {}
        self._counter_dict = {} # A counter dict to order the data we grab from each page.
        # self.current_link = ''
        self._cat_imgs_to_save = {}
        self._s3_client = boto3.client('s3')
        self._xpath_dict = {

            'official_user_container': '//div[@data-test-id="official-user-attribution"]',
            'official_user_element': './/div[@class="tBJ dyH iFc yTZ pBj zDA IZT mWe CKL"]',
            'non_off_user_container': '//div[@data-test-id="user-rep"]',
            'non_off_user_element': './/div[@class="tBJ dyH iFc yTZ pBj zDA IZT mWe"]',
            'tag_container': '//div[@data-test-id="CloseupDetails"]',
            'story_tag_container': '//div[@data-test-id="CloseupMainPin"]',
            'reg_title_element': '//div[@data-test-id="CloseupDetails"]//div[@data-test-id="pinTitle"]/h1/div',
            'h1_title_element': '//div[@data-test-id="CloseupMainPin"]//h1',
            'desc_container': '//div[@data-test-id="CloseupDetails"]//div[@data-test-id="CloseupDescriptionContainer"]',
            'desc_element': './/span[@class="tBJ dyH iFc yTZ pBj zDA IZT swG"]',
            'links_container': '//div[@data-test-id="grid"]//div[@class="vbI XiG"]',
            'links_element': './/div[@class="Yl- MIw Hb7"]/div/div/div/div[1]/a',
            'categories_container': '//div[@data-test-id="interestRepContainer"]'
        }

        self._driver.get(self._root)

    ''' TODO: Talk to Blair about our over-reliance on attributes and if it's an issue. '''

    def _get_category_links(self, categories_xpath: str) -> dict:
        """Extract the href attribute of each of the categories
        
        Args
        ---------------------
        categories_xpath: str
        
        Return
        ---------------------
        dict: dictionary containing the href of each category
        """
        # self._driver.get(self._root)
        # Get the a list of all the categories

        try:
            container = WebDriverWait(self._driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, categories_xpath))
                )
            categories = container.find_elements_by_xpath('.//a')
            # Extract the href
            return {i+1:link.get_attribute('href') for i, link in enumerate(categories)}
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _print_options(self, category_link_dict: dict):
        """Print all categories available on the homepage

        Args
        ---------------------
        category_link_dict: dict
        """
        try:
            print(f"\n The options (Total {len(category_link_dict)}) are:")

            # Print all categories available on the route page
            for idx, category in category_link_dict.items():
                print(f"\t {idx}: {category.replace(self._root, '').split('/')[0]}")
            # Is a return needed here to test?
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _categories_to_save_imgs(self, selected_category_names) -> None:

        try:
            get_any = ''
            while get_any != 'N' and get_any != 'Y':
                get_any = input('\nWould you like to download images for \
any of the selected categories? Y or N: ').upper()
                if get_any == 'Y':
                    print('A = All categories: ')
                    download_check = ['A']
                    for index, category in enumerate(selected_category_names):
                        print(f'{index + 1} = {category}')
                        download_check.append(str(index + 1))
                    while True:
                        try:
                            downloads = input('\nPlease select which categories you would \
like to download images for.\nEnter your answer as a comma separated list: ').upper()
                            downloads = (downloads.replace(' ', '')).split(',')
                            repeat_check = []
                            for option in downloads:
                                repeat_check.append(option)
                                assert option in download_check
                            assert len(repeat_check) == len(set(repeat_check))
                            if 'A' in downloads:
                                for cat_name in selected_category_names:
                                    self._cat_imgs_to_save[cat_name] = True
                            else:
                                for option in downloads:
                                    self._cat_imgs_to_save[selected_category_names[int(option) - 1]] = True
                                for name in selected_category_names:
                                    if name not in self._cat_imgs_to_save.keys():
                                        self._cat_imgs_to_save[name] = False
                            print_list = [key for key, value in self._cat_imgs_to_save.items() if value == True]
                            print(f'\nDownloading images for {print_list}')
                            break
                        except KeyboardInterrupt:
                            raise KeyboardInterrupt
                        except:
                            print('\nPlease only select options from the provided list. No duplicates. ')
                elif get_any == 'N':
                    print('\nNo images will be downloaded. ')
                    for cat_name in selected_category_names:
                        self._cat_imgs_to_save[cat_name] = False
                else:
                    print('\nNot a supported input. Please retry: ')
        except KeyboardInterrupt:
            raise KeyboardInterrupt


    def _get_user_input(self, category_link_dict: dict) -> List[str]:  
        """Let user decide how many and which categories to download
        
        Args
        ---------------------
        category_link_dict: dict
        """
        try: 
            while True:
                try:
                    categories_num = int(input(f"\nHow many categories of images \
do you wish to grab? 1 to {len(category_link_dict)}: \n"))
                    assert 0 < categories_num <= len(category_link_dict)
                    break
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:  
                    print(f"\nInvalid input, try again.") 

            self.selected_category = {}

            if categories_num == len(category_link_dict):
                self.selected_category = category_link_dict
            else:
                try:
                    choices = []
                    check_list = [str(x+1) for x in range(len(category_link_dict))]

                    while len(choices) != categories_num:
                        choices = input(f"\nPlease select your desired categories. \
Separate your choices by commas. You have {categories_num} choice(s) to make: ")

                        choices = (choices.replace(' ', '')).split(',')
                        print(choices)
                        for choice in choices:
                            if choice not in check_list:
                                choices = []
                                print(f'\nPlease only enter integers in a comma separated \
list. Values between 1 and {len(category_link_dict)}: ') 
                                break
                        if len(choices) == 0:
                            continue
                        elif len(choices) != categories_num:
                            print('\nPlease only select the predetermined number of choices. ')
                        elif len(set(choices)) != len(choices):
                            print('\nOnly unique categories accepted. ')
                            choices = []
                        elif len(set(choices)) == len(choices) == categories_num:
                            for i, choice in enumerate(choices):
                                choice = int(choice)
                                self.selected_category[i+1] = category_link_dict[choice]
                        else: 
                            print('\nUnknown choice error')  
                except KeyboardInterrupt:
                    raise KeyboardInterrupt          
                except:
                    raise Exception(f"\nChoice error 2")

            self.selected_category_names = [category.split('/')[4] for category in self.selected_category.values()]
            print(f"Categories selected: {self.selected_category_names}")

            return self.selected_category_names

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def create_RDS(self):
        """Ask for user input whether a RDS needs to be created
        and if so, whether it needs to be remotely created or locally"""
        try:
            valid = False
            while not valid:
                rds_answer =  input("Do you want to create an RDS? [Y/n]:").lower()
                if rds_answer == 'y' or rds_answer == 'n':
                    valid = True

                    if rds_answer == 'y':
                        print('Creating RDS...')
                        # Ask whether to create/update tables on AWS RDS or local RDS
                        remote_RDS = input("Do you want a remote AWS RDS? [Y/n]: ").lower()
                        if remote_RDS == 'y': # Remote
                            self._json_to_rds('../data/', True)
                        elif remote_RDS == 'n': # Local
                            self._json_to_rds('../data/', False)
                        else:
                            raise Exception('Invalid answer')
                    else:
                        print('Data will not be saved in an RDS...')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _interior_cloud_save_loop(self, remote: str) -> Union[None, str]:

        ''' Defines the interior loop of the cloud save function. Would all have been in one function but I needed to repeat
            this section of code if the user made an error entering their bucket name. 
            
            Arguments: remote 
            
            Returns: "retry" if user made a mistake when entering their bucket name
                      None at all other times '''

        try:
            if remote == 'Y':
                self.s3_bucket = input('\nPlease enter the name of your desired S3 bucket. ')
                go_on = ''
                while go_on != 'Y' and go_on != 'N':
                    go_on = input(f'\nYou have entered {self.s3_bucket} as your s3 bucket. \
Is this correct? Y or N: ').upper()
                    if go_on == 'Y':
                        print('A = All categories: ')
                        upload_check = ['A']
                        for index, category in enumerate(self.selected_category_names):
                            print(f'{index + 1} = {category}')
                            upload_check.append(str(index + 1))
                        while True:
                            try:
                                all_or_some = input('\nWhich categories would you like to download \
to this bucket?\nPlease enter your choice as a comma separated \
list: ').upper()
                                all_or_some = (all_or_some.replace(' ', '')).split(',')
                                print(all_or_some)
                                repeat_check = []
                                for option in all_or_some:
                                    repeat_check.append(option)
                                    assert option in upload_check
                                assert len(repeat_check) == len(set(repeat_check))
                                if 'A' in all_or_some:
                                    self._s3_list = self.selected_category_names
                                else:
                                    for option in all_or_some:
                                        self._s3_list.append(self.selected_category_names[int(option) - 1])
                                break
                            except KeyboardInterrupt:
                                raise KeyboardInterrupt
                            except:
                                print('\nPlease only select options from the provided list. No duplicates. ')

                    elif go_on == 'N':
                        print('\nPlease re-enter the name of your bucket. ')
                        return 'retry'
            elif remote == 'N':
                print('\nAll data will be stored on your local machine. ')
            else:
                print('\nYour selection was not valid, please choose again. ')
                return ''

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _save_to_cloud_or_local(self) -> None:

        try:
            remote = ''
            while remote != 'N' and remote != 'Y':
                if remote == '':
                    remote = input('\nWould you like to save any of \
your data/images to a remote bucket? Y or N: ').upper()
                    remote = self._interior_cloud_save_loop(remote)
                    if remote == None:
                        break
                elif remote == 'retry':
                    remote = 'Y'
                    remote = self._interior_cloud_save_loop(remote)
                    if remote == None:
                        break
                else:
                    print('\nLoop structure error. Luke you stupid...')

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _initialise_local_folders(self, directory_path, selected_category_names) -> None:

        ''' Defines a function which initialises folders for
            local saves. 
            
            Arguments: directory_path: str 
            
            Returns: None '''

        try:
            self._root_save_path = directory_path

            print(f"\nCreating folders. ")

            for category in selected_category_names:
                # Create a folder named data to store a folder for each category
                if not os.path.exists(f'{self._root_save_path}'):
                    os.makedirs(f'{self._root_save_path}')
                self._main_dict[f"{category}"] = {}
                os.makedirs(f'{self._root_save_path}/temp_{category}')
        except KeyboardInterrupt:
            raise KeyboardInterrupt
            
    def _initialise_counter(self, selected_category_names) -> dict:

        try:
            for category in selected_category_names:
                self._counter_dict[f'{category}'] = 0

            return self._counter_dict
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _check_for_logs(self) -> None:

        ''' Defines a function which checks to see where/if there is previous data from which to 
            continue. This would need to read from log.json and recent_saves.json '''

        
        ''' Need to find if current run cats are being saved to a different location than 
            their previous save. If so we then transfer all data to new location and delete old.
            Better than current method.
            
            Something like:
            
                for save in saves:
                    if old_save_location != new_save_location: # Check new_save_location by self._s3_list
                        copy all data from old save to new save        and self.s3_bucket
                        make sure all data is in the correct dict
                        delete old save.
                        
            Easy peasy? '''        

        ''' So, new_save_location needs to be defined after user has made all their choices. Needs to be done for save in saves.
            In order to get this:
                - When user says they want to save to bucket, save bucket as bucket. Will have self.bucket anyway.
                - If not self.bucket then new_save_loc = local.
                - If self.bucket then for each category in self._s3_list and in saves, new_save_loc = [remote, s3_bucket]
                  else: new_save_loc = local '''
        try: 
            if os.path.exists('../data/recent-save-log.json'):
                #[if x in current_cat_list? for x in recent_save.values()]
                # if recent_save.values()
                # current_cat_list 
                with open('../data/recent-save-log.json', 'r') as load:
                    recent_saves = json.load(load)
                saves = [key for key in recent_saves if key in self.selected_category_names]
                with open('../data/log.json', 'r') as load:
                    contents = json.load(load)
                    tuples_content = [(item[0], item[1]) for item in contents]
                if saves:
                    print(f'\nWe have detected saved data for the follow categories: {saves}. ')
                    fresh = ''
                    while fresh != 'Y' and fresh != 'N':
                        fresh = input('\nWould you like to add to your existing data? Y or N: ').upper()
                        if fresh == 'Y':
                            self._link_set = set(tuples_content)
                            self._log = set(tuples_content)
                            for cat, href in tuples_content:
                                category = cat.split('/')[0]
                                if category in self.selected_category_names:
                                    self._counter_dict[category] += 1
                            for save in saves:
                                if recent_saves[save] == 'local':
                                    with open(f'../data/{save}/{save}.json', 'r') as load:
                                        self._main_dict[f'{save}'] = json.load(load)
                                elif recent_saves[save][0] == 'remote':
                                    obj = self._s3_client.get_object(
                                        Bucket = recent_saves[save][1],
                                        Key = (f'pinterest/{save}/{save}.json')
                                    ) 
                                    self._main_dict[f'{save}'] = json.loads(obj['Body'].read())
                                else: 
                                    print('\nSomething fishy going on with the save_log. ')
                        elif fresh == 'N':
                            tuples_content = [item for item in tuples_content if item[0].split('/')[0] not in saves]
                            self._link_set = set(tuples_content)
                            self._log = set(tuples_content)
                        else:
                            print('\nPlease re-enter your input. ')
                else:
                    self._link_set = set(tuples_content)
                    self._log = set(tuples_content)
                    fresh = None
                    print("Previous saves detected: None relate to this data collection run. ")
            else:
                fresh = None
            return fresh

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _extract_links(self, container_xpath: str, elements_xpath: str, n_scrolls = 1) -> None:
        """Move to the page of a category and extract src attribute for the images 
            at the bottom of the page
            
        Args
        ---------------------
        container_xpath: str 
        elements_xpath: str
        """
        try:
            self._driver.get(self._root + self._category)
            Y = 10**6   # Amount to scroll down the page   
            sleep(2)

            # Keep scrolling down for a number of times
            for _ in range(n_scrolls):
                self._driver.execute_script(f"window.scrollTo(0, {Y})")  # Scroll down the page
                sleep(1)
                # Store the link of each image if the page contains the targeted images
                try:
                    container = self._driver.find_element_by_xpath(container_xpath)
                    link_list = container.find_elements_by_xpath(elements_xpath)
                    print(f"\nNumber of images successfully extracted: {len(link_list)}")
                    self._link_set.update([(self._category, link.get_attribute('href')) for link in link_list])
                    print(f"\nNumber of uniques images: {len(self._link_set) - len(self._log)}")
                except: 
                    print('\nSome errors occurred, most likely due to no images present')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_images_src(self, n_scrolls=1) -> None:
        """Get src links for all images
        
        Args:
        ---------------------
        n_scrolls - Number of times to scroll through a page
        """
        try:
            # Loop through each category
            for category in self.selected_category.values():
                self._category = category.replace(self._root, "")
                self._category_image_count[self._category] = 0
                self._extract_links(self._xpath_dict['links_container'], 
                                    self._xpath_dict['links_element'],
                                    n_scrolls)
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _generate_unique_id(self) -> None:

        ''' Defines a function which generates a unique ID (uuid4) for every image page
            that is scraped by the scraper. 
            
            Arguments: None
            
            Returns: None '''
        try:
            self._current_dict['unique_id'] = str(uuid.uuid4())
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_title(self, title_element) -> None:

        ''' Defines a function that grabs the title from a Pinterest page
            and adds it to the key "title" in self._current_dict.
            
            Arguments: title_element
            
            Returns: None '''
        try:
            try:
                title_element = self._driver.find_element_by_xpath(title_element)
                self._current_dict["title"] = title_element.get_attribute('textContent')
            except: # No title attribute found
                self._current_dict["title"] = 'No Title Data Available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        
    def _grab_description(self, desc_container, desc_element) -> None:

        ''' Defines a function that grabs the description from a Pinterest page
            and adds it to the key "description" in self._current_dict.
            
            Arguments: desc_container, desc_element
            
            Returns: None '''
        try: 
            description_container = self._driver.find_element_by_xpath(desc_container)
            try: # Need this try statement to see if the description is present. Other wise it faults if there is no description.
                description_element = WebDriverWait(description_container, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, desc_element))
                )
                self._current_dict["description"] = description_element.get_attribute('textContent')
            except:
                self._current_dict["description"] = 'No description available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_user_and_count(self, dict_container, dict_element) -> None:

        ''' Defines a function that grabs the poster name and follower count
            and appends adds them to the keys "poster_name" and "follower_count"
            respectively in self._current_dict.
            
            Arguments: dict_container, dict_element
            
            Returns: None '''
        try:
            try:
                container = self._driver.find_element_by_xpath(dict_container)
                poster_element = container.find_element_by_xpath(dict_element)          
                self._current_dict["poster_name"] = poster_element.get_attribute('textContent')
                # TODO: Replace the hard coded xpath
                follower_element =  container.find_elements_by_xpath('.//div[@class="tBJ dyH iFc yTZ pBj zDA IZT swG"]')
                followers = follower_element[-1].get_attribute('textContent')
                # If statement is needed as if there is no associated text I cannot use .split to grab only the value.
                # Do not want the text "followers" on the end to clean the data somewhat.
                if followers == '': # If the element has no associated text, there are no followers. Think this is redunant for official users.
                    self._current_dict["follower_count"] = '0'
                else:
                    self._current_dict["follower_count"] = followers.split()[0]
            except:
                if 'poster_name' not in self._current_dict.keys():
                    self._current_dict['poster_name'] = 'User Info Error'
                if 'follower_count' not in self._current_dict.keys():
                    self._current_dict['follower_count'] = 'User Info Error'
                print('User Info Error')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_tags(self, tag_container) -> None:

        ''' Defines a function that grabs the tags from a Pinterest page
            and adds them to the key "tag_list" in self._current_dict.
        
            Arguments: tag_container
            
            Returns: None '''
        try: 
            # TODO:Replace any hard coded xpath
            try:
                container = WebDriverWait(self._driver, 0.5).until(
                    EC.presence_of_element_located((By.XPATH, f'{tag_container}//div[@data-test-id="vase-carousel"]'))
                )
                tag_elements = container.find_elements_by_xpath('.//div[@data-test-id="vase-tag"]//a')
                self._current_dict["tag_list"] = [tag.get_attribute('textContent') for tag in tag_elements]
            except:
                self._current_dict["tag_list"] = 'No Tags Available'
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _download_image(self, src: str) -> None:
        """Download the image either remotely or locally
        """
        try:
            if self._cat_imgs_to_save[self._category]:
                # if self._category not in self._s3_list: # Save locally
                urllib.request.urlretrieve(src, 
                f"{self._root_save_path}/temp_{self._category}/{self._category}_{self._counter_dict[self._category]}.jpg")
            else:
                self._current_dict['downloaded'] = False
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _is_img_downloaded(self) -> None:
        try:
            if 'downloaded' not in self._current_dict.keys():
                self._current_dict['downloaded'] = True
            else:
                pass
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _save_location_key(self) -> None:
        try:
            if self._category in self._s3_list:
                self._current_dict['save_location'] = f"S3 bucket: {self.s3_bucket}"
            else:
                self._current_dict['save_location'] = f"Local save in /data/{self._category}"
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_image_src(self) -> None:

        ''' Defines a function that grabs the image src from a Pinterest page
            and adds it to the key "image_src" in self._current_dict.
            If there is no image and instead a video, grabs the video src
            and adds it to the key "video_src" in self._current_dict.
            
            Arguments: None
            
            Returns: None '''
        try:
            try:
                try: # Need this try statement to see if image in an image or other media type.
                    image_element = WebDriverWait(self._driver, 1).until(
                        EC.presence_of_element_located((By.XPATH, '//div[@data-test-id="pin-closeup-image"]//img'))
                    )
                    self._current_dict["is_image_or_video"] = 'image'
                    self._current_dict["image_src"] = image_element.get_attribute('src')
                    self._download_image(self._current_dict["image_src"])
                    self._is_img_downloaded()
                    self._save_location_key()
                except:
                    video_element = self._driver.find_element_by_xpath('//video')
                    self._current_dict["is_image_or_video"] = 'video'
                    self._current_dict["image_src"] = video_element.get_attribute('poster')
                    self._download_image(self._current_dict["image_src"])
                    # Cannot get video src as the link doesn't load. Can instead get the video thumbnail.
                    self._is_img_downloaded()
                    self._save_location_key()
            except:
                self._current_dict['downloaded'] = False
                self._save_location_key()
                print('\nImage grab Error. Possible embedded video (youtube).')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_story_image_srcs(self) -> None:

        ''' Function in testing. Third page layout (story) that has different html
            tabs to target to get info I need. Should be able to integrate later on
            in to one larger function which pulls for xpath dict. '''
        try:
            try: 
                try: # TODO: Remove hard coded xpath 
                    _ = WebDriverWait(self._driver, 1).until(
                            EC.presence_of_element_located((By.XPATH, '//div[@aria-label="Story Pin image"]'))
                        )
                    image_container = self._driver.find_element_by_xpath('//div[@aria-label="Story Pin image"]')
                    image = image_container.get_attribute('style')
                    if not image:
                        self._current_dict["is_image_or_video"] = 'video(story page format)'
                        video_container = self._driver.find_element_by_xpath('//div[@data-test-id="story-pin-closeup"]//video')
                        self._current_dict["image_src"] = video_container.get_attribute('poster')
                        self._download_image(self._current_dict["image_src"])
                        # This particular case no longer seems useful. Leaving it in place in case it turns out to be useful in larger data_sets.
                        self._is_img_downloaded()
                        self._save_location_key()
                    else: 
                        self._current_dict["is_image_or_video"] = 'image(story page format)'
                        self._current_dict["image_src"] = re.split('\"', image)[1]
                        self._download_image(self._current_dict["image_src"])
                        self._is_img_downloaded()
                        self._save_location_key()
                    # This will only grab the first couple (4 I believe) images in a story post.
                    # Could improve.
                except:
                    self._current_dict["is_image_or_video"] = 'multi-video(story page format)'
                    video_container = self._driver.find_element_by_xpath('//div[@data-test-id="story-pin-closeup"]//video')
                    self._current_dict["image_src"] = video_container.get_attribute('poster')
                    self._download_image(self._current_dict["image_src"])
                    self._is_img_downloaded()
                    self._save_location_key()
            except:
                self._current_dict['downloaded'] = False
                self._save_location_key()
                print('\nStory image grab error.')
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_all_users_and_counts(self) -> None:

        ''' Defines a function that checks if a user is officially recognised or
            a story. If official, runs official-user data grab, if not, runs non-official-user
            data grab or story_grab if a story.
        
            Arguments: None
            
            Returns: None '''
        try: 
            if (self._driver.find_elements_by_xpath('//div[@data-test-id="official-user-attribution"]')):
                self._generate_unique_id()
                self._grab_title(self._xpath_dict['reg_title_element'])
                self._grab_description(self._xpath_dict['desc_container'], self._xpath_dict['desc_element'])
                self._grab_user_and_count(
                    self._xpath_dict['official_user_container'],
                    self._xpath_dict['official_user_element']
                )
                self._grab_tags(self._xpath_dict['tag_container'])
                self._grab_image_src()
            elif (self._driver.find_elements_by_xpath('//div[@data-test-id="CloseupDetails"]')):
                self._generate_unique_id()
                self._grab_title(self._xpath_dict['reg_title_element'])
                self._grab_description(self._xpath_dict['desc_container'], self._xpath_dict['desc_element'])
                self._grab_user_and_count(
                    self._xpath_dict['non_off_user_container'],
                    self._xpath_dict['non_off_user_element']
                )
                self._grab_tags(self._xpath_dict['tag_container'])
                self._grab_image_src()
            else:
                self._generate_unique_id()
                self._grab_title(self._xpath_dict['h1_title_element'])
                self._current_dict["description"] = 'No description available Story format'
                self._grab_user_and_count(
                    self._xpath_dict['non_off_user_container'],
                    self._xpath_dict['non_off_user_element']
                )
                self._grab_tags(self._xpath_dict['story_tag_container'])
                self._grab_story_image_srcs()
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _grab_page_data(self) -> None:

        ''' Defines a function which combines all data grabs and loops
            though all page links to grab the data from each page
            
            Arguments: None
            
            Returns: None '''

        # category_link_dict = self._get_category_links('//div[@data-test-id="interestRepContainer"]//a')
        try:
            fresh_set = self._link_set.difference(self._log)
            for (cat, link) in tqdm(list(fresh_set)):
                self._category = cat.split("/")[0]
                self._counter_dict[f"{self._category}"] += 1
                self._current_dict = {}
                # self.current_link = link Use link directly
                self._driver.get(link)
                self._grab_all_users_and_counts()
                self._main_dict[f"{self._category}"][f"{self._category}_{self._counter_dict[self._category]}"] = self._current_dict
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _data_dump(self) -> None:

        ''' Defines a function which dumps the compiled dictionary
            to a json file.
            
            Arguments: None
            
            Returns: None '''
        try:    
            if not os.path.exists('../data'):
                os.mkdir('../data')
            os.chdir('..')
            os.chdir('data')

            print('Dumping Data: ')
            for name in tqdm(self.selected_category_names):
                with open(f'temp_{name}/{name}.json', 'w') as loading:
                    json.dump(self._main_dict[f"{name}"], loading)

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _data_transferal(self) -> None:

        ''' Defines a function which moves data from temp folders to it's final destination.
            Data is handled in this way to remove errors when KeyboardInterrupting the scraping process. '''
        try:

            print('Moving files around a bit... ')

            for category in tqdm(self.selected_category_names):
                
                temp_path = f'../data/temp_{category}'
                # For local saves
                if category not in self._s3_list:
                    end_path = f'../data/{category}'
                    # If this is the first run
                    # Or old data deleted with fresh == N
                    if not os.path.exists(end_path):
                        os.rename(temp_path, end_path)
                    # If end folder already exists from previous run
                    # I.e. fresh == Y
                    else:
                        for file in os.listdir(temp_path):
                            shutil.move(f'{temp_path}/{file}', f'{end_path}/{file}')
                        shutil.rmtree(temp_path)
                # For remote saves:
                else:
                    end_path = f'pinterest/{category}'
                    for file in os.listdir(temp_path):
                        self._s3_client.upload_file(
                            f'{temp_path}/{file}',
                            self.s3_bucket,
                            f'{end_path}/{file}'
                    )
                    shutil.rmtree(temp_path)
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _create_recent_or_new(self, path: str) -> None:

        ''' Defines the inner function to _create_log and passes the function the correct
            log save name depending on if it's an initial run or not. 
            
            Arguments: path 
            
            Returns: that log.json and path exist for tesing.  '''
        try:

            with open('../data/log.json', 'w') as log, open(path, 'w') \
                as save:
                    json.dump(list(self._link_set), log)
                    json.dump(self.recent_save_dict, save)
            
            return os.path.exists('../data/log.json') and os.path.exists(path)
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _create_log(self) -> bool:

        ''' Defines a function which creates two logs. One of which logs pages visited as to not repeat
            the other a log of where the most recent save for each category is in order to update the
            most recent save. 
            
            Arguments: None
            
            Returns: None '''
        try:

            # if dict exists json.load
            print('Creating save logs: ')
            if os.path.exists('../data/recent-save-log.json'):
                with open('../data/recent-save-log.json', 'r') as load:
                    self.recent_save_dict = json.load(load)
            # NEED TO DO SOMETHING HERE WITH NEW SAVE AND RECENT SAVE
            else:
                self.recent_save_dict = {}
            # For each category, check if the images should be saved remotely or locally
            for category in tqdm(self.selected_category_names):
                if category in self._s3_list:
                    update = ['remote', self.s3_bucket]
                else:
                    update = 'local'
                self.recent_save_dict[category] = update
            with open('../data/log.json', 'w') as log, open('../data/recent-save-log.json', 'w') \
            as save:
                json.dump(list(self._link_set), log)
                json.dump(self.recent_save_dict, save)
            
            return os.path.exists('../data/log.json') and os.path.exists('../data/recent-save-log.json')

        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _delete_old_files(self, fresh) -> None:

        ''' Defines a function that deletes old save files if they become outdated. 

            Arguments: fresh

            Returns: None '''
        try:
            if fresh:

                with open('../data/recent-save-log.json', 'r') as load:
                    old_saves = json.load(load)
                saves = [key for key in old_saves if key in self.selected_category_names] 

                for save in saves:

                    if save in self._s3_list and old_saves[save][0] == 'remote' \
                    and old_saves[save][1] == self.s3_bucket:
                        # If user wants to start anew, still need to delete old data.
                        if fresh == 'N':
                            s3 = boto3.resource('s3')
                            bucket = s3.Bucket(old_saves[save][1])
                            bucket.objects.filter(Prefix=f"pinterest/{save}/").delete()
                    # If save remote and new bucket diff: move and delete
                    elif save in self._s3_list and old_saves[save][0] == 'remote' \
                    and old_saves[save][1] != self.s3_bucket:
                        s3 = boto3.resource('s3')
                        src_bucket = s3.Bucket(old_saves[save][1])
                        target_bucket = s3.Bucket(self.s3_bucket)
                        print('Relocating previous bucket save files. ')
                        for src in tqdm(src_bucket.objects.filter(Prefix=f"pinterest/{save}/")):
                            # Move any items from remote bucket in to new remote bucket.
                            if fresh == 'Y':
                                copy_source = {
                                    'Bucket': src_bucket.name,
                                    'Key': src.key
                                }
                                target_bucket.copy(copy_source, src.key)
                                # Delete old file.
                                src.delete()
                            elif fresh == 'N':
                                # Delete old file.
                                src.delete()
                    # If save remote and no new bucket: move local and delete
                    elif save not in self._s3_list and old_saves[save][0] == 'remote':
                        s3 = boto3.resource('s3')
                        src_bucket = s3.Bucket(old_saves[save][1])
                        print('Relocating previous bucket save files. ')
                        for src in tqdm(src_bucket.objects.filter(Prefix=
                        f"pinterest/{save}/")):
                            # Move any items from remote bucket in to new local folder.
                            if fresh == 'Y':
                                src_bucket.download_file(src.key, 
                                f"../data/temp_{save}/{src.key.split('/')[2]}")
                                # Delete old remote file.
                                src.delete()
                            elif fresh == 'N':
                                # Delete old remote file.
                                src.delete()
                    # If save local and new save local: pass
                    elif save not in self._s3_list and old_saves[save] == 'local':
                        # If user wants to start anew, still need to delete old data.
                        if fresh == 'N':
                            shutil.rmtree(f'../data/{save}')
                    # If save local and new save remote: move and delete
                    elif save in self._s3_list and old_saves[save] == 'local':
                        s3 = boto3.resource('s3')
                        print('Relocating previous local save files. ')
                        for item in tqdm(os.listdir(f'../data/{save}')):
                            # Move any items from local to new remote bucket.
                            if fresh == 'Y':
                                self._s3_client.upload_file(f'../data/{save}/{item}', 
                                self.s3_bucket, f'pinterest/{save}/{item}')
                            elif fresh == 'N':
                                pass
                        # Delete old local file
                        shutil.rmtree(f'../data/{save}')
                    else: 
                        print('Missed a scenario in _delete_old_files. ')
                        self._driver.quit()
                        
        except KeyboardInterrupt:
            raise KeyboardInterrupt

    def _connect_to_RDS(self, remote):
        
        DATABASE_TYPE = 'postgresql'
        DBAPI = 'psycopg2'

        # ENDPOINT = None
        # if remote:
        #     ENDPOINT = input('AWS endpoint: ') # Change it for your AWS endpoint

        USER = input('User (default = postgres): ')
        if not USER:
            USER = 'postgres'
        PASSWORD = input('Password: ')
        
        HOST = input('Host (default = localhost): ')
        if not HOST:
            HOST = 'localhost'

        PORT = input('Port (default = 5433): ')
        if not PORT:
            PORT = 5433
        DATABASE = input('Database (default = Pagila): ')
        if not DATABASE:
            DATABASE = 'Pagila'

        if remote:
            ENDPOINT = input('AWS endpoint: ') # Change it for your AWS endpoint
            engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{ENDPOINT}:{PORT}/{DATABASE}")
        else:
            engine = create_engine(f"{DATABASE_TYPE}+{DBAPI}://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}")

        engine.connect()

        return engine

    def _process_df(self, df):
        '''Rearrange the dataframe in the proper format before returning
        sending to a RDS.
        Args: 
            df: pandas dataframe to process
        Return: None'''

        df = df.T
        df['name'] = df.index
        # df['id'] = list(range(len(df)))
        # df = df.set_index('uuid4')
        df = df.set_index('unique_id')
        file_name_col = df.pop('name')
        df.insert(0, 'name', file_name_col)
        print(df.head(3))
        return df

    def _json_to_rds(self, data_path:str, remote: bool):
        '''Loads the JSON files from both AWS or locally and turns
        the data into RDS.
        
        Args:
            data_path: local path (directory) where the json files are stored
            remote: boolean whether to create/update RDS on AWS
        
        Return: None'''

        # Connect to RDS
        engine = self._connect_to_RDS(remote)

        # Find all local JSON files
        folders = os.listdir(data_path)
        recent_log = folders[folders.index('recent-save-log.json')]
        with open(data_path + '/' + recent_log) as log_file:
            recent_saves = json.load(log_file)

        # Check content of log to check if the data are on S3 or in local PC
        for key, val in recent_saves.items():
            if type(val) == str: # For local JSON files
                json_path = data_path + '/' + key + '/' + key +'.json'
                print(json_path)
                # Load local JSON file
                df = pd.read_json(json_path)
                df = self._process_df(df)
                df.to_sql(f'pinterest_{key}', engine, if_exists='replace')

            elif type(val) == list: # For remote JSON files
                # Load file from S3 bucket
                json_obj = self._s3_client.get_object(
                    Bucket = val[1],
                    Key = (f'pinterest/{key}/{key}.json')
                )
                save_dict = json.loads(json_obj['Body'].read())
                df = pd.DataFrame.from_dict(save_dict)
                df = self._process_df(df)
                df.to_sql(f'pinterest_{key}', engine, if_exists='replace')


    def get_category_data(self) -> None:
        """Public function that combines all the functionality implemented in the 
        class to scrap the webpages
        """
        try:
            category_link_dict = self._get_category_links(self._xpath_dict['categories_container'])
            sleep(0.75)
            self._print_options(category_link_dict)
            selected_category_names = self._get_user_input(category_link_dict)
            self._categories_to_save_imgs(selected_category_names)
            self._save_to_cloud_or_local()
            self._initialise_counter(selected_category_names)
            self._initialise_local_folders('../data', selected_category_names)
            fresh = self._check_for_logs()
            while True:
                try:
                    scrolling_times = int(input('\nHow many times to scroll through each page \
(~5 to 10 images on average per scroll)?: '))
                    break
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:
                    print('Invalid input, try again: ')
            self._grab_images_src(n_scrolls=scrolling_times)
            self._grab_page_data()
            self._delete_old_files(fresh)
            self._data_dump()
            print('Please do not end the script now. May cause errors with later runs. ')
            self._data_transferal()
            log_created = self._create_log()
            # self._create_RDS()
            self._driver.quit()
        except KeyboardInterrupt:
            print('\nTerminating Script.\nRemoving any accumulated data. ')
            if self.selected_category_names:
                for category in tqdm(self.selected_category_names):
                    if os.path.exists(f'../data/temp_{category}'):
                        shutil.rmtree(f'../data/temp_{category}')
            exit()

if __name__ == "__main__": 

    pinterest_scraper = PinterestScraper('https://www.pinterest.co.uk/ideas/')
    # Scrap the website
    pinterest_scraper.get_category_data()
    # Create RDS from collected data
    pinterest_scraper.create_RDS()

    # A lot of the attributes shouldn't be attributes. Try to make functions that return something as an attribute return
    # it as an actual return to pass it into the following function.

    # TODO: if after scroll 1 list len = 0, move on to next category.
    # TODO: prometheus and grafana
    # TODO: Docstring and annotate properly.

    ''' TODO: For the delete to work properly.

        Can use a for loop.

        Create a func to turn new saves in to currnt nomenclature. 
        
        Scenarios: 

        - Not continue from old data in same loc:
            - Before run starts: 
                - Data stays where it is.
                - Temp folder for new data gets created.
            - During run:
                - Except: KeyboardInterrupt: New folder gets deleted 
            - Once run ends: 
                - Save new folder, delete old one, rename new one.
        - Not continue from old data in new loc:
            - Before run starts: 
                - Data stays where it is.
                - New folder created in new loc.
            - During run:
                - Except: KeyboardInterrupt: New folder gets deleted
            - Once run ends: 
                - Old file deleted when new one saves.
        - Continue from old data in same loc:
            - Before run starts: 
                - Data stays where it is.
                - Temp folder for new data made.
            - During run:
                - Except: KeyboardInterrupt: New folder deleted -> New folder deleted
            - Once run ends: 
                - Move old data in to new folder after new save delete old save,
                  rename new save.
        - Continue from old data in new loc:
            - Before run starts: 
                - Data stays where it is.
                - New folder created in new loc.
            - During run:
                - Except: KeyboardInterrupt: New folder gets deleted
            - Once run ends: 
                - Old data moved to new folder after new save.

     '''

    ''' Make temp folders for all, even s3 cats. Push to s3 at the end. Saves potential deletion from s3 using resources.
        Made temp folders. 
        Data being added to temp folders.
        
        To do after, if keyboard interrupt, delete temp folders.
        
        Moved data to proper folders and deleted old.
             '''