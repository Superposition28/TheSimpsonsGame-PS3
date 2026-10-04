
#include "Str_Load.h"
#include "Str_Load_Full.h"
#include "Str_Confirmer.h"
#include "TXDOpen.h"
#include "RWSOpen.h"
#include "DFFOpen.h"
#include "BSPOpen.h"
#include <iostream>
#include <fstream>
#include <ostream>
#include <math.h>
#include <memory>
#include <chrono>
#include <numeric>
#include <atomic>

double StandardDev(const std::vector<double>& times, double &mean)
{
	if (times.size() <= 1) 
	{
		// if nothing then exit
		return 0.0; 
	}

	// calculate the sum of times
	double sum = std::accumulate(times.begin(), times.end(), 0.0);

	//mean calculation
	mean = sum / times.size();

	
	double sq_sum = 0.0;
	for (double time : times)
	{
		sq_sum += (time - mean) * (time - mean);
	}

	// calculate the standard deviation
	double variance = sq_sum / (times.size() - 1);
	return std::sqrt(variance);
}


void run(std::vector<double>& strAdd, std::vector<double>& modelAdd) {

	int counter = 0;



	if (std::filesystem::exists("AllAssets")) {

		std::vector<std::filesystem::directory_entry> entries;

		for (const auto& entry : std::filesystem::directory_iterator("AllAssets")) {
			if (!entry.is_directory()) {
				entries.push_back(entry);
			}
		}


		for (int i = 0; i < entries.size(); i++) {
			std::string exitPath;

			std::string entryPath = entries[i].path().string();

			std::string prefix = "AllAssets";



			// this will extract the file name, - 3 for the extentsion and AllAssets because of the folder, this does work now
			exitPath.insert(exitPath.begin(), entryPath.begin() + prefix.length() + 1, entryPath.end() - 4);

			if (!std::filesystem::exists(exitPath.c_str())) {
				std::filesystem::create_directory(exitPath.c_str());


			}
		

			Str_Confirmer* ConfirmStreamFile = new Str_Confirmer();
			ConfirmStreamFile->Init(entryPath.c_str());
			int Global = ConfirmStreamFile->ReadHeader();

			if (Global == 0) {



				Str_Load* StrObject = new Str_Load();

				StrObject->USFP = exitPath + "/" + "Uncompressed_Sections";
				StrObject->ExtractedSection = exitPath + "/" + "Files";

				StrObject->init(entryPath.c_str()); // land of chocolate zone02
				StrObject->CheckHeaderForCompression();
				StrObject->UnCompress();
				StrObject->ExtractFiles();



				delete StrObject;
			}

			else if (Global == 1) {
				Str_Load_Full* StrObject = new Str_Load_Full();

				StrObject->USFP = exitPath + "/" + "Uncompressed_Sections";
				StrObject->ExtractedSection = exitPath + "/" + "Files";

				StrObject->init(entryPath.c_str()); // land of chocolate zone02
				StrObject->CheckHeaderForCompression();
				StrObject->UnCompress();
				StrObject->ExtractFiles();


				delete StrObject;
			}

			delete ConfirmStreamFile;

			int ModelCounter = 0;

			if (std::filesystem::exists(exitPath)) {

				std::vector<std::filesystem::directory_entry> subEntries;

				for (const auto& subEntry : std::filesystem::directory_iterator(exitPath + "/" + "Files")) {
					if (!subEntry.is_directory()) {
						subEntries.push_back(subEntry);
					}
				}


				std::cout << exitPath << " " << "/" << "Files" << std::endl;



				for (int j = 0; j < subEntries.size(); j++) {

					std::string entryPath = subEntries[j].path().string();

					std::string extension;

					extension.insert(extension.begin(), entryPath.end() - 4, entryPath.end());


					// these are files that contain geometry
					if (extension != ".rws" && extension != ".dff" && extension != ".txd" && extension != ".bsp") {
						continue;
					}



					if (extension == ".rws") {


						RwsOpen* RwsObject = new RwsOpen(entryPath);

						RwsObject->FilePath = exitPath;
						RwsObject->GlobalFileIndex = counter++;

						RwsObject->Init();
						RwsObject->ExtractData();


						ModelCounter++;
						delete RwsObject;
					}

					else if (extension == ".dff") {


						DFFOpen* DffObject = new DFFOpen(entryPath);

						DffObject->FilePath = exitPath;
						DffObject->GlobalFileIndex = counter++;

						DffObject->Init();
						DffObject->ExtractData();

						ModelCounter++;
						delete DffObject;

					}

					else if (extension == ".txd") {
						TXDOpen* TXDObject = new TXDOpen(entryPath);

						TXDObject->FilePath = exitPath;
						TXDObject->GlobalFileIndex = counter++;

						TXDObject->Init();
						TXDObject->ExtractData();

						delete TXDObject;
					}

					/*	else if (extension == ".bsp") {
							BSPOpen* BSPObject = new BSPOpen(entryPath);

							BSPObject->FilePath = exitPath;
							BSPObject->GlobalFileIndex = counter++;

							BSPObject->Init();
							BSPObject->ReadHeader();
							BSPObject->WriteToFile();

							delete BSPObject;
						}*/




				}




			}


			exitPath.clear();

		}
	}
}

void runMulti(std::vector<double>& strAdd, std::vector<double>& modelAdd) {

	std::atomic<int> counter = 0;
	


	if (std::filesystem::exists("AllAssets")) {

		std::vector<std::filesystem::directory_entry> entries;

		for (const auto& entry : std::filesystem::directory_iterator("AllAssets")) {
			if (!entry.is_directory()) {
				entries.push_back(entry);
			}
		}

		

		#pragma omp parallel for

		for (int i = 0; i < entries.size(); i++) {
			std::string exitPath;

			std::string entryPath = entries[i].path().string();

			std::string prefix = "AllAssets";



			// this will extract the file name, - 3 for the extentsion and AllAssets because of the folder, this does work now
			exitPath.insert(exitPath.begin(), entryPath.begin() + prefix.length() + 1, entryPath.end() - 4);

			if (!std::filesystem::exists(exitPath.c_str())) {
				std::filesystem::create_directory(exitPath.c_str());


			}
			


			Str_Confirmer* ConfirmStreamFile = new Str_Confirmer();
			ConfirmStreamFile->Init(entryPath.c_str());
			int Global = ConfirmStreamFile->ReadHeader();

			if (Global == 0) {



				Str_Load* StrObject = new Str_Load();

				StrObject->USFP = exitPath + "/" + "Uncompressed_Sections";
				StrObject->ExtractedSection = exitPath + "/" + "Files";

				StrObject->init(entryPath.c_str()); // land of chocolate zone02
				StrObject->CheckHeaderForCompression();
				StrObject->UnCompress();
				StrObject->ExtractFiles();



				delete StrObject;
			}

			else if (Global == 1) {
				Str_Load_Full* StrObject = new Str_Load_Full();

				StrObject->USFP = exitPath + "/" + "Uncompressed_Sections";
				StrObject->ExtractedSection = exitPath + "/" + "Files";

				StrObject->init(entryPath.c_str()); // land of chocolate zone02
				StrObject->CheckHeaderForCompression();
				StrObject->UnCompress();
				StrObject->ExtractFiles();


				delete StrObject;
			}

			delete ConfirmStreamFile;

			if (std::filesystem::exists(exitPath)) {

				std::vector<std::filesystem::directory_entry> subEntries;

				for (const auto& subEntry : std::filesystem::directory_iterator(exitPath + "/" + "Files")) {
					if (!subEntry.is_directory()) {
						subEntries.push_back(subEntry);
					}
				}


				std::cout << exitPath << " " << "/" << "Files" << std::endl;

				#pragma omp parallel for

				for (int j = 0; j < subEntries.size(); j++) {

					std::string entryPath = subEntries[j].path().string();

					std::string extension;

					extension.insert(extension.begin(), entryPath.end() - 4, entryPath.end());


					// these are files that contain geometry
					if (extension != ".rws" && extension != ".dff" && extension != ".txd" && extension != ".bsp") {
						continue;
					}



					if (extension == ".rws") {


						RwsOpen* RwsObject = new RwsOpen(entryPath);

						RwsObject->FilePath = exitPath;
						RwsObject->GlobalFileIndex = counter++;

						RwsObject->Init();
						RwsObject->ExtractData();


						delete RwsObject;
					}

					else if (extension == ".dff") {


						DFFOpen* DffObject = new DFFOpen(entryPath);

						DffObject->FilePath = exitPath;
						DffObject->GlobalFileIndex = counter++;

						DffObject->Init();
						DffObject->ExtractData();


						delete DffObject;

					}

					/*else if (extension == ".txd") {
						TXDOpen* TXDObject = new TXDOpen(entryPath);

						TXDObject->FilePath = exitPath;
						TXDObject->GlobalFileIndex = counter++;

						TXDObject->Init();
						TXDObject->ExtractData();

						delete TXDOpen;
					}*/

					/*	else if (extension == ".bsp") {
							BSPOpen* BSPObject = new BSPOpen(entryPath);

							BSPObject->FilePath = exitPath;
							BSPObject->GlobalFileIndex = counter++;

							BSPObject->Init();
							BSPObject->ReadHeader();
							BSPObject->WriteToFile();

							delete BSPObject;
						}*/




				}




			}

		
			exitPath.clear();

		}
	}
}


void AddToRunTime(int HowMany, std::vector<double>& strAdd, std::vector<double>& modelAdd) {

	for (int i = 0; i < HowMany; i++) {
		run(strAdd, modelAdd);
	}

}


int main(int argc, char** argv) {

	auto start = std::chrono::high_resolution_clock::now();

	std::vector<double> strAdd;
	std::vector<double> modelAdd;

	AddToRunTime(1,strAdd, modelAdd);
	
	double strMean = 0.0f;
	double modelMean = 0.0f;

	double strTime = StandardDev(strAdd, strMean);
	double modelTime = StandardDev(modelAdd, modelMean);
	
	
	auto end = std::chrono::high_resolution_clock::now();

	auto duration = std::chrono::high_resolution_clock::duration(end - start);


	
	

	

	
	return 0;
};