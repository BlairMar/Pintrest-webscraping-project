from selenium import webdriver     
from webdriver_manager.chrome import ChromeDriverManager 
from webdriver_manager import driver
from src import pinterestScraper       
import unittest
driver = webdriver.Chrome(ChromeDriverManager().install()) 
webdriver.Chrome('/Users/danielzakaiem/Downloads/chromedriver')
import unittest.mock  
import os


class PinterestScraperTestCase(unittest.TestCase):

     
    def setUp(self):   
        self.pinterest_scraper = pinterestScraper.PinterestScraper(root = 'https://www.pinterest.co.uk/ideas/', category = "thanksgiving/949410256396" )
        self._root = 'https://www.pinterest.co.uk/ideas/'
    
    def tearDown (self):
        self.pinterest_scraper._driver.close()  
        """
        This function is used to set up the scenario for each test
        """
    def test_get_category_links_1 (self): 
        """
        This funtion is used to see if a dictionary is created
        """
        test_dict = self.pinterest_scraper._get_category_links('//div[@data-test-id="interestRepContainer"]//a')
        self.assertIsInstance(test_dict, dict) 

    def test_get_category_links_2 (self):
         """
         This function is used to test if the correct href attributes are extracted
         """
         test_href_links = self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div')  
        
         hand_picked_category_xpaths = ['//*[@id="mweb-unauth-container"]/div/div/div/div[3]/div/a',  
                                       '//*[@id="mweb-unauth-container"]/div/div/div/div[6]/div/a',
                                       '//*[@id="mweb-unauth-container"]/div/div/div/div[9]/div/a']
         hand_picked_category_hrefs = []
         for xpath in hand_picked_category_xpaths:
             hand_picked_category_hrefs.append(self.pinterest_scraper._driver.find_element_by_xpath(xpath).get_attribute('href'))
         counter = 0
         for ele in hand_picked_category_hrefs:   
            if ele in test_href_links.values():
                counter +=1
                print(counter)
         self.assertEqual(counter, 3) 

    def test_get_category_links_3(self):
        """
        This function is used to test if the correct hrefs are placed into the dictionary
        """
        dict_of_hrefs = self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div') 
        handpicked_hrefs = ['https://www.pinterest.co.uk/ideas/thanksgiving/949410256396/',   
        'https://www.pinterest.co.uk/ideas/holidays/910319220330/',  
        'https://www.pinterest.co.uk/ideas/animals/925056443165/', 
        'https://www.pinterest.co.uk/ideas/architecture/918105274631/',
        'https://www.pinterest.co.uk/ideas/art/961238559656/', 
        'https://www.pinterest.co.uk/ideas/beauty/935541271955/',
        'https://www.pinterest.co.uk/ideas/design/902065567321/', 
        'https://www.pinterest.co.uk/ideas/diy-and-crafts/934876475639/', 
        'https://www.pinterest.co.uk/ideas/education/922134410098/', 
        'https://www.pinterest.co.uk/ideas/electronics/960887632144/', 
        'https://www.pinterest.co.uk/ideas/event-planning/941870572865/', 
        'https://www.pinterest.co.uk/ideas/finance/913207199297/',
        'https://www.pinterest.co.uk/ideas/food-and-drink/918530398158/',
        'https://www.pinterest.co.uk/ideas/lawn-and-garden/909983286710/',
        'https://www.pinterest.co.uk/ideas/home-decor/935249274030/', 
        'https://www.pinterest.co.uk/ideas/mens-fashion/924581335376/', 
        'https://www.pinterest.co.uk/ideas/quotes/948192800438/', 
        'https://www.pinterest.co.uk/ideas/tattoos/922203297757/',
        'https://www.pinterest.co.uk/ideas/travel/908182459161/',
        'https://www.pinterest.co.uk/ideas/vehicles/918093243960/',
        'https://www.pinterest.co.uk/ideas/weddings/903260720461/',
        'https://www.pinterest.co.uk/ideas/womens-fashion/948967005229/',
        'https://www.pinterest.co.uk/ideas/thanksgiving/949410256396/']
        list_of_hrefs = [*dict_of_hrefs.values()] 
        counter = 0
        i = 0
        for element in list_of_hrefs:
            category = handpicked_hrefs[i]
            counter += (element.count(category)) 
            i += 1 
        self.assertEqual(counter, 22) 

    def test_print_options (self):
        """
        This function is used to test if the entire method is run properly
        """
        category_link_dict = self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div')
        test = self.pinterest_scraper._print_options(category_link_dict)
        self.assertEqual(test, True)
    
    # Requires 22 user inputs.
    def test_categories_to_save_imgs (self):
        """
        This function is used to test if any of the categories available can successfully be inputted 
        """
        # Outputs a list of all categories available- thus user will haveto input one/more of these.
        potential_categories_selected = (self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div')).values() 
        # Ascertain that any of these inputs will suffice.
        counter = 0
        for category in potential_categories_selected:
            if self.pinterest_scraper._categories_to_save_imgs(category) == True:
                print ("This category can be passed in to the method")
                counter +=1
            else:
                print ("This category can not be passed into the method")
        self.assertEqual(counter, 22)
    
    def test_get_user_input_1 (self):
        """
        This function is used to test if the correct list of values is out-putted
        """
        # Outputs hrefs to each category in an enumerated dictionary.
        category_link_dict =  self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div')
        # Outputs a list of the categories selected  eg ['christmas', 'holidays'].
        test_output = self.pinterest_scraper._get_user_input(category_link_dict)[0]  
        # Selected category/ies should be within included in this list.
        list_should_include = []
        values = category_link_dict.values()
        for  category in values:
            list_should_include.append(category.replace(self._root, '').split('/')[0])
        # 'Correct' catgory names included in the list appends false to list (x), so list should be all false values.
        x = [] 
        for element in test_output: 
            if element in list_should_include:
                x.append(False)  
        # Testoutputted list should be included in 'list_should_include' as it should be one or more of those categories.
        self.assertTrue(not any(x))  

    def test_get_user_input_2 (self):
        """1
        This function is used to test if the correct object types are outputted
        """
        counter = 0
        category_link_dict =  self.pinterest_scraper._get_category_links('//*[@id="mweb-unauth-container"]/div/div/div')
        test_output = self.pinterest_scraper._get_user_input(category_link_dict)  
        if type(test_output[0]) == list and type(test_output[1]) == dict:
            counter +=1
        self.assertEqual(counter, 1)  
 

  # User must haveto type in RDS details manually.
    def test_create_RDS (self):
        """
        This function is used to test if the entire method is run properly
        """
        test = self.pinterest_scraper.create_RDS()
        self.assertEqual(test, True)


    def test_initialise_local_folders (self): 
        """
        This function is used to test if the correct folders are created
        """                                                              
        # First we call the command to make the 3 folders.
        self.pinterest_scraper._initialise_local_folders('/Users/danielzakaiem/Downloads', [ 'thanksgiving', 'architecture', 'electronics']) 
        folders_created = ['/Users/danielzakaiem/Downloads/thanksgiving/',  
         '/Users/danielzakaiem/Downloads/architecture/',
          '/Users/danielzakaiem/Downloads/electronics/']
        counter = 0
        for folder in folders_created:
          if os.path.isdir(folder):
            print('Folder exists')
            counter += 1
        else:
             print ('Folder does not exist')
        self.assertEqual(counter, 3) 
    
 
    def test_initialise_counter_1 (self,x):
        """
        This function is used to test if the output is a dictionary
        """
        selected_category_names = [ 'thanksgiving', 'architecture', 'electronics']
        test = self.pinterest_scraper._initialise_counter(selected_category_names)
        self.assertIsInstance(test, dict)

    
     # Makes sure that dictionary has the specific keys {'thanksgiving': 0, 'architecture': 0, 'electronics': 0}.
    def test_initialise_counter_2 (self):
         """
         This function is used to test if the correct keys are in the out-putted dictionary
         """
         selected_category_names = ['thanksgiving', 'architecture', 'electronics']
         test = self.pinterest_scraper._initialise_counter(selected_category_names) 
         selected_categories = [ 'thanksgiving', 'architecture', 'electronics']
         counter = 0
         for category in selected_categories:
            if category in test:
                print ("Correct category added")
                counter += 1
            else:
                print ("This is not the category that should have been added!")

         self.assertEqual (counter, 3)
         
            
    def check_for_logs (self):
         """
         This function is used to make sure that the entire method is run
         """
         test = self.pinterest_scraper._check_for_logs()
         self.assertEqual(test, True)
            
if __name__ == "__main__":
    unittest.main(argv= [''],verbosity=2,exit =False)  
