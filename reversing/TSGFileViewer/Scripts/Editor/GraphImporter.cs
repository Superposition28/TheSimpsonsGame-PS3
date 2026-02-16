using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Assets.Scripts;
using UnityEditor;
using UnityEditor.VersionControl;
using UnityEngine;

namespace Assets.Scripts.Editor
{
	internal class GraphImporter
	{
		[MenuItem("Window/Simpsons/Graph")]
		private static void CreateNavGraphs()
		{
			var defaultAssets = Selection.GetFiltered<DefaultAsset>(SelectionMode.Assets);

			var textAssetPaths = new List<string>();

			// create TextAssets for each graph
			foreach (var asset in defaultAssets)
			{
				var bytes = File.ReadAllBytes(AssetDatabase.GetAssetPath(asset));
				var path = AssetDatabase.GetAssetPath(asset);

				var changedExtension = Path.ChangeExtension(path, "bytes");
				//var textAsset = new TextAsset(text);
				textAssetPaths.Add(changedExtension);
				//AssetDatabase.CreateAsset(textAsset, changedExtension);
				File.WriteAllBytes(changedExtension, bytes);
				AssetDatabase.ImportAsset(changedExtension);
			}

			AssetDatabase.Refresh();

			foreach (var item in textAssetPaths)
			{
				var textAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(item);

				var newGO = new GameObject(textAsset.name);
				var graph = newGO.AddComponent<NavigationGraph>();
				graph.GraphFile = textAsset; graph.OnButtonClicked();
			}
		}

		[MenuItem("Window/Simpsons/Graph", true)]
		private static bool ValidateCreateNavGraphs()
		{
			var defaultAssets = Selection.GetFiltered<DefaultAsset>(SelectionMode.Assets);

			return defaultAssets.Length != 0 && defaultAssets.Select(AssetDatabase.GetAssetPath).All(path => Path.GetExtension(path) == ".graph");
		}
	}
}
