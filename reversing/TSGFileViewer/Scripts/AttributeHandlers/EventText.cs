using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace Assets.Scripts.AttributeHandlers
{
	public class EventText : AttributeHandler
	{
		public string Unknown0;
		public string Unknown1;
		public int Unknown2;
		public int Unknown3;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Unknown0 = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						Unknown1 = reader.ReadNullTerminatedString();
						break;

					case 2:
						Unknown2 = attr.Data.ToInt32BigEndian();
						break;

					case 3:
						Unknown3 = attr.Data.ToInt32BigEndian();
						break;

					default:
						throw new NotImplementedException();
				}
			}
		}
	}
}
