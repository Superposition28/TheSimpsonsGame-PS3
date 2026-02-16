using Assets.Scripts.Resources;
using RWReader;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using RWReader.Sections;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Assets.Scripts.ResourceHandlers
{
	[Serializable]
	public class rwID_TEXDICTIONARY : Resource
	{
		[SerializeField]
		public Section SectionTree;
	}

	public class rwID_TEXDICTIONARY_Handler : ResourceHandler
	{
		public Dictionary<Guid128, rwID_TEXDICTIONARY> TextureDictionaries = new();
		public List<Guid128> DebugList = new();
		public List<TextureNative> DebugList2 = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var section = new RWStreamReader().Read(data);

			var texDict = new rwID_TEXDICTIONARY();
			texDict.STRFile = strFilePath;
			texDict.GUID = guid;
			texDict.SectionTree = section;

			foreach (var item in section.GetChildren<TextureNative>())
			{
				DebugList2.Add(item);
			}

			TextureDictionaries.Add(guid, texDict);
			DebugList.Add(guid);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return TextureDictionaries.Values.ToList();
		}
	}
}
