using UnityEditor;
using UnityEngine;

namespace Editor
{
	class STRLoader : EditorWindow
	{
		string loadSTRButton = "Load STR";
		string filePath = "";
		string usrdirfolder = "";

		[MenuItem("Window/Simpsons/STR")]
		public static void ShowWindow()
		{
			EditorWindow.GetWindow(typeof(STRLoader));
		}

		void OnGUI()
		{
			usrdirfolder = GUILayout.TextField(usrdirfolder);
			filePath = GUILayout.TextField(filePath);

			EditorGUILayout.BeginHorizontal();
			if (GUILayout.Button(loadSTRButton))
			{
				if (filePath != "")
				{
					SDBMHash.PrecomputeHashes();
					EAStreamFile.LoadSTRFile(usrdirfolder, filePath);
				}
			}
			EditorGUILayout.EndHorizontal();
		}
	}
}