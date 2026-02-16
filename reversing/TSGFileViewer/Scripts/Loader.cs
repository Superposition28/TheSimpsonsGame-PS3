using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace Assets.Scripts {
	public class Loader : MonoBehaviour {
		public string UsrdirFolder;

		public List<string> StrFilesToLoad = new List<string>() {
			"frontend/frontend"
		};

		private void Start() {
			SDBMHash.PrecomputeHashes();

			foreach (var item in StrFilesToLoad) {
				EAStreamFile.LoadSTRFile(UsrdirFolder, item);
			}
		}
	}
}
