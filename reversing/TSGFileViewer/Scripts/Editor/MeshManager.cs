using System;
using System.Collections.Generic;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Assets.Scripts.Editor
{
	class MeshManager : EditorWindow
	{
		string findMeshButton = "Find Mesh";
		string loadMeshGeoButton = "Load Mesh";
		string filePath = "No mesh loaded!";

		[MenuItem("Window/Simpsons/Mesh")]
		public static void ShowWindow()
		{
			EditorWindow.GetWindow(typeof(MeshManager));
		}

		void OnGUI()
		{
			GUILayout.Label("Load Mesh", EditorStyles.boldLabel);
			if (GUILayout.Button(findMeshButton))
			{
				filePath = EditorUtility.OpenFilePanelWithFilters("Load Mesh", "", new string[] { "Renderware Binary Streams", "rws.PS3.preinstanced,dff.PS3.preinstanced" });
			}
			GUILayout.Label(filePath, EditorStyles.miniLabel);
			EditorGUILayout.BeginHorizontal();
			if (GUILayout.Button(loadMeshGeoButton))
			{
				if (filePath != "No mesh loaded!")
				{
					var filters = new List<MeshFilter>();
					var meshes = MeshLoader.LoadTSGMesh(filePath);
					foreach (var mesh in meshes)
					{
						var meshObj = new GameObject(mesh.name);
						var mf = meshObj.AddComponent<MeshFilter>();
						mf.sharedMesh = mesh;
						filters.Add(mf);

						var isSkinned = mesh.boneWeights != null && mesh.boneWeights.Length > 0;

						if (isSkinned)
						{
							var skinned = meshObj.AddComponent<SkinnedMeshRenderer>();

							var bones = new List<Transform>();
							var i = 0;
							foreach (var item in mesh.bindposes)
							{
								var go = new GameObject($"Bindpose {i++}");
								go.transform.position = item * new Vector4(0, 0, 0, 1);
								bones.Add(go.transform);
							}

							skinned.bones = bones.ToArray();
							skinned.sharedMesh = mesh;
							skinned.rootBone = bones[0];
						}
						else
						{
							meshObj.AddComponent<MeshRenderer>();
						}


						var tsg = meshObj.AddComponent<TSGMesh>();
						meshObj.transform.localScale = new Vector3(1, 1, 1);
						meshObj.transform.localPosition = Vector3.zero;
					}

					for (var i = 0; i < filters.Count; i++)
					{
						var newFilePath = filePath.Substring(filePath.IndexOf("/build/PS3"));
						newFilePath = newFilePath.Substring(0, newFilePath.LastIndexOf("/"));

						var savePath = $"Assets/Meshes{newFilePath}/{filters[i].sharedMesh.name}";

						var splits = savePath.Split("/");

						string storedPath = "Assets";
						for (int j = 1; j < splits.Length - 1; j++)
						{
							if (!AssetDatabase.IsValidFolder($"{storedPath}/{splits[j]}"))
							{
								AssetDatabase.CreateFolder(storedPath, splits[j]);
							}

							storedPath += $"/{splits[j]}";
						}

						AssetDatabase.CreateAsset(filters[i].sharedMesh, savePath + ".asset");
					}
				}
			}
			EditorGUILayout.EndHorizontal();
			EditorGUILayout.Space();
			GUILayout.Label("Selected Mesh", EditorStyles.boldLabel);
			var obj = Selection.activeGameObject;
			MeshFilter filter = null;
			if (obj == null)
			{
				GUILayout.Label("No object selected", EditorStyles.miniLabel);
			}
			else
			{
				filter = obj.GetComponent<MeshFilter>();
				if (filter != null)
				{
					GUILayout.Label(filter.sharedMesh.name, EditorStyles.miniLabel);
					GUILayout.Label($"Verts : {filter.sharedMesh.vertices.Length}", EditorStyles.miniLabel);
					GUILayout.Label($"Tris : {filter.sharedMesh.triangles.Length}", EditorStyles.miniLabel);
					GUILayout.Label($"Faces : {filter.sharedMesh.triangles.Length / 3}", EditorStyles.miniLabel);

					foreach (var item in filter.sharedMesh.uv)
					{
						GUILayout.Label($"{item}", EditorStyles.miniLabel);
					}
				}
			}
		}
	}
}
