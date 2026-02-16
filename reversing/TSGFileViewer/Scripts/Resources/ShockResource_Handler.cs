using Assets.Scripts.ResourceHandlers;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Assets.Scripts.Resources
{
	public class ShockResource_Handler : ResourceHandler
	{
		public Dictionary<Guid128, ShockResource> ShockResources = new();
		public List<ShockResource> DebugList = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var config = new ShockResource(data);
			config.STRFile = strFilePath;
			config.GUID = guid;

			ShockResources.Add(guid, config);
			DebugList.Add(config);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return ShockResources.Values.ToList();
		}
	}
}