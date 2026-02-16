using Assets.Scripts.ResourceHandlers;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Assets.Scripts.Resources
{
	public class LightTOC_Handler : ResourceHandler
	{
		public Dictionary<Guid128, LightTOC> LightTOCs = new();
		public List<LightTOC> DebugList = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var toc = new LightTOC(data);
			toc.STRFile = strFilePath;
			toc.GUID = guid;

			LightTOCs.Add(guid, toc);
			DebugList.Add(toc);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return LightTOCs.Values.ToList();
		}
	}
}