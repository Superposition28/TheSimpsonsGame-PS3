using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class DebugText : AttributeHandler
	{
		public string m_targetName;
		public string m_pDebugStr;
		public float m_displayTime = 4.0f;
		public uint m_options = 1;

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
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_pDebugStr = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						m_displayTime = attr.Data.ToSingleBigEndian();
						break;
					}

					case 3:
					{
						m_options = attr.Data.ToUInt32BigEndian();
						break;
					}
				}
			}
		}
	}
}