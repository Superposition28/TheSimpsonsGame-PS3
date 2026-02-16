using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class TriggerAuto : AttributeHandler
	{
		public string m_targetName;
		public float m_delay;
		public uint m_options;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_targetName = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
					{
						m_delay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 2:
					{
						m_options = attr.Data.ToUInt32BigEndian();
						break;
					}
				}
			}
		}
	}
}
