using Assets.Scripts.ResourceHandlers;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Assets.Scripts.Resources
{
	public class TextOverlayFile_Handler : ResourceHandler
	{
		public Dictionary<Guid128, TextOverlayFile> TextOverlayFiles = new();
		public List<TextOverlayFile> DebugList = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var overlay = new TextOverlayFile(data);
			overlay.STRFile = strFilePath;
			overlay.GUID = guid;

			TextOverlayFiles.Add(guid, overlay);
			DebugList.Add(overlay);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return TextOverlayFiles.Values.ToList();
		}
	}
}