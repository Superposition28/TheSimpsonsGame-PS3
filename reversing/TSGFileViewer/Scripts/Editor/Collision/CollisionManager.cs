using Editor.Collision.HavokReader;
using UnityEditor;
using UnityEngine;

namespace Editor.Collision
{
	class CollisionManager : EditorWindow
	{
		string findColliderButton = "Find Collider";
		string loadColliderButton = "Load Collider";
		string filePath = "No collider loaded!";

		[MenuItem("Window/Simpsons/Collision")]
		public static void ShowWindow()
		{
			EditorWindow.GetWindow(typeof(CollisionManager));
		}

		void OnGUI()
		{
			GUILayout.Label("Load Mesh", EditorStyles.boldLabel);
			if (GUILayout.Button(findColliderButton))
			{
				filePath = EditorUtility.OpenFilePanel("Load Collider", "", "hkt.PS3,hko,hko.PS3");
			}
			GUILayout.Label(filePath, EditorStyles.miniLabel);
			EditorGUILayout.BeginHorizontal();
			if (GUILayout.Button(loadColliderButton))
			{
				if (filePath != "No collider loaded!")
				{
					var reader = new HavokBinaryReader();
					reader.Read(filePath);
				}
			}
			EditorGUILayout.EndHorizontal();
		}
	}
}
