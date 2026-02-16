using Assets.Scripts.ResourceHandlers;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Assets.Scripts.Resources
{
	public class ControllerEventConfig_Handler : ResourceHandler
	{
		public Dictionary<Guid128, ControllerEventConfig> ControllerEventConfigs = new();
		public List<ControllerEventConfig> DebugList = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			var config = new ControllerEventConfig(data);
			config.STRFile = strFilePath;
			config.GUID = guid;

			ControllerEventConfigs.Add(guid, config);
			DebugList.Add(config);
		}

		public override IEnumerable<Resource> GetResources()
		{
			return ControllerEventConfigs.Values.ToList();
		}
	}
}
