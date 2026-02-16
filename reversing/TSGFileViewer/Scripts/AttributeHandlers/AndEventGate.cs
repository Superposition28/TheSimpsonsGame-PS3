using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class AndEventGate : AttributeHandler
	{
		public string m_inputEvent01;
		public string m_inputEvent02;
		public string m_inputEvent03;
		public string m_inputEvent04;
		public string m_outputEvent;
		public string m_resetEvent;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_inputEvent01 = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_inputEvent02 = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_inputEvent03 = reader.ReadNullTerminatedString();
						break;
					}

					case 3:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_inputEvent04 = reader.ReadNullTerminatedString();
						break;
					}

					case 4:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_outputEvent = reader.ReadNullTerminatedString();
						break;
					}

					case 5:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_resetEvent = reader.ReadNullTerminatedString();
						break;
					}
				}
			}
		}
	}
}
